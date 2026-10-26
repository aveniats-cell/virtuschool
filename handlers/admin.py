import json
from telegram import Update
from telegram.ext import ContextTypes

from db import (
    is_admin, user_is_admin, get_admin_id,
    list_students, list_groups, get_group, get_or_create_group,
    students_not_in_group, set_user_group, pending_students,
    get_user, weighted_avg, last_grades, student_progress,
    create_assignment, get_assignment, delete_assignment,
    assignments_in_group, create_grade, create_announcement,
    all_student_ids,
)
from keyboards import (
    admin_menu_kb, admin_back_kb, admin_create_type_kb, admin_grade_source_kb,
    admin_yes_no_kb, groups_kb, groups_kb_with_new, groups_pick_kb,
    students_kb, assignments_kb,
)
from states import (
    ADM_CREATE_Q, ADM_CREATE_OPTIONS, ADM_CREATE_CORRECT, ADM_CREATE_ANSWER,
    ADM_CREATE_THEORY, ADM_GRADE, ADM_BROADCAST, ADM_HW_TEXT,
    ADM_ANN_TEXT, ADM_ANN_WHEN, ADM_ANN_WHERE, ADM_GROUP_NAME,
)


# ---------------- /admin и меню ----------------

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_is_admin(update.effective_user):
        await update.message.reply_text("У вас нет прав администратора.")
        return
    await show_admin_menu(update, context)


async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = None
    text = "Здравствуйте, вы администратор бота.\nМеню:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=admin_menu_kb())
    else:
        await update.message.reply_text(text, reply_markup=admin_menu_kb())


async def back_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["state"] = None
    await q.edit_message_text("Админ-панель:", reply_markup=admin_menu_kb())


# ---------------- УЧЕНИКИ ----------------

async def admin_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["picking_for"] = "view"
    rows = list_students()
    if not rows:
        await q.edit_message_text("Учеников пока нет.", reply_markup=admin_back_kb())
        return
    await q.edit_message_text(
        "Все ученики (нажми для профиля):",
        reply_markup=students_kb(rows),
    )


async def admin_student_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: int):
    user = get_user(uid)
    if not user:
        await update.callback_query.edit_message_text("Ученик не найден.", reply_markup=admin_back_kb())
        return

    avg = weighted_avg(uid)
    avg_s = avg if avg is not None else "None"
    grades = last_grades(uid, 5)
    progress = student_progress(uid)

    lines = [
        f"👤 {user[1]} (id {uid})",
        f"Пол: {user[2]}",
        f"Группа: {user[5] if user[5] else '—'}",
        f"Средневзвешенная: {avg_s}",
        "",
        "Последние оценки:",
    ]
    if not grades:
        lines.append("— оценок нет")
    else:
        src_ru = {"lesson": "занятие", "homework": "д/з", "video": "видео"}
        for v, c, s, d in grades:
            lines.append(f"  {v} — {c or '—'} ({src_ru.get(s, s)})")

    lines.append("")
    lines.append("Прогресс по заданиям:")
    if not progress:
        lines.append("— заданий нет")
    else:
        for aid, atype, is_hw, is_correct in progress[:10]:
            mark = "—" if is_correct is None else ("✅" if is_correct else "❌")
            tag = "Д/З" if is_hw else "Задание"
            lines.append(f"  #{aid} [{atype}] {tag}: {mark}")

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Поставить оценку", callback_data=f"adm_give_{uid}")],
        [InlineKeyboardButton("Назад", callback_data="admin_students")],
    ])
    context.user_data["grade_target"] = uid
    await update.callback_query.edit_message_text("\n".join(lines), reply_markup=kb)


# ---------------- ОЦЕНКА ----------------

async def admin_grade_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["picking_for"] = "grade"
    rows = list_students()
    if not rows:
        await q.edit_message_text("Учеников пока нет.", reply_markup=admin_back_kb())
        return
    await q.edit_message_text("Выберите ученика:", reply_markup=students_kb(rows))


async def admin_give_grade(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: int):
    context.user_data["grade_target"] = uid
    context.user_data["picking_for"] = None
    await update.callback_query.edit_message_text(
        "Выбери источник оценки:", reply_markup=admin_grade_source_kb()
    )


async def admin_grade_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["grade_source"] = q.data.replace("gsource_", "")
    context.user_data["state"] = ADM_GRADE
    await q.edit_message_text(
        "Введи оценку в формате: `2-5 - пояснение`\n"
        "Например: `3 - не совсем готова`"
    )


async def on_adm_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if " - " in text:
        v_str, comment = text.split(" - ", 1)
    else:
        v_str, comment = text, ""
    try:
        value = int(v_str.strip())
        assert 2 <= value <= 5
    except (ValueError, AssertionError):
        await update.message.reply_text("Оценка должна быть числом от 2 до 5. Формат: `3 - комментарий`")
        return

    uid = context.user_data.get("grade_target")
    source = context.user_data.get("grade_source", "lesson")
    if not uid:
        await update.message.reply_text("Не удалось определить ученика. Вернись в меню.")
        context.user_data["state"] = None
        return

    create_grade(uid, value, comment.strip(), source)
    context.user_data["state"] = None
    context.user_data.pop("grade_target", None)
    context.user_data.pop("grade_source", None)

    await update.message.reply_text(
        f"✅ Оценка {value} выставлена ученику {uid}.",
        reply_markup=admin_menu_kb(),
    )


# ---------------- СОЗДАТЬ ЗАДАНИЕ ----------------

async def admin_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["create_payload"] = {}
    context.user_data["create_is_hw"] = False
    await q.edit_message_text("Выберите тип задания:", reply_markup=admin_create_type_kb())


async def ctype_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["create_type"] = "choice"
    context.user_data["create_payload"] = {}
    context.user_data["state"] = ADM_CREATE_Q
    await q.edit_message_text("Напишите текст задания.\nНапример: `Salve, come stai? _`")


async def ctype_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["create_type"] = "translate"
    context.user_data["create_payload"] = {}
    context.user_data["state"] = ADM_CREATE_Q
    await q.edit_message_text(
        "Введите текст для перевода:\n"
        "Например: `Salve, come va?` или `Здравствуй! Как дела?`"
    )


async def ctype_write(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["create_type"] = "write"
    context.user_data["create_payload"] = {}
    context.user_data["state"] = ADM_CREATE_Q
    await q.edit_message_text(
        "Введите вопрос/задание (например: `Напиши по-итальянски: спасибо`)"
    )


async def ctype_theory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["create_type"] = "theory"
    context.user_data["create_payload"] = {}
    context.user_data["state"] = ADM_CREATE_THEORY
    await q.edit_message_text("Введите текст теории.")


async def on_adm_create_q(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = context.user_data.get("create_payload", {})
    payload["question"] = update.message.text.strip()
    context.user_data["create_payload"] = payload
    ctype = context.user_data.get("create_type")

    if ctype == "choice":
        context.user_data["state"] = ADM_CREATE_OPTIONS
        await update.message.reply_text(
            "Введите варианты ответа через `|` (от 2 до 10):\n"
            "Например: `E tu?|Allora!|Arrivederci|Prego`"
        )
    else:  # translate / write
        context.user_data["state"] = ADM_CREATE_ANSWER
        await update.message.reply_text("Введите правильный ответ:")


async def on_adm_create_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    options = [o.strip() for o in raw.split("|") if o.strip()]
    if not (2 <= len(options) <= 10):
        await update.message.reply_text("Нужно от 2 до 10 вариантов, разделённых `|`.")
        return
    payload = context.user_data["create_payload"]
    payload["options"] = options
    context.user_data["create_payload"] = payload
    context.user_data["state"] = ADM_CREATE_CORRECT
    await update.message.reply_text(
        "Какой вариант правильный? Введите его текст точно как в списке:"
    )


async def on_adm_create_correct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text.strip()
    payload = context.user_data["create_payload"]
    options = payload.get("options", [])
    if answer not in options:
        await update.message.reply_text(
            "Такого варианта нет в списке. Введите одно из: " + ", ".join(options)
        )
        return
    payload["correct_index"] = options.index(answer)
    payload["answer"] = answer
    context.user_data["create_payload"] = payload
    context.user_data["state"] = None
    await ask_group_for(update, context, action="create")


async def on_adm_create_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = context.user_data["create_payload"]
    payload["answer"] = update.message.text.strip()
    context.user_data["create_payload"] = payload
    context.user_data["state"] = None
    await ask_group_for(update, context, action="create")


async def on_adm_create_theory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = context.user_data["create_payload"]
    payload["text"] = update.message.text.strip()
    context.user_data["create_payload"] = payload
    context.user_data["state"] = None
    await ask_group_for(update, context, action="create")


async def ask_group_for(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    groups = list_groups()
    if not groups:
        await update.message.reply_text(
            "Сначала создай хотя бы одну группу (Меню → Группы → ➕ Новая группа).",
            reply_markup=admin_menu_kb(),
        )
        return
    context.user_data["grp_pick_action"] = action
    await update.message.reply_text(
        "Какой группе дать это?",
        reply_markup=groups_pick_kb(groups),
    )


async def grp_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    gid = int(q.data.replace("grp_pick_", ""))
    action = context.user_data.get("grp_pick_action")

    if action == "create":
        ctype = context.user_data.get("create_type")
        payload = context.user_data.get("create_payload")
        is_hw = context.user_data.get("create_is_hw", False)
        create_assignment(ctype, payload, gid, is_homework=is_hw)
        context.user_data.pop("create_payload", None)
        context.user_data.pop("create_type", None)
        context.user_data["grp_pick_action"] = None
        await q.edit_message_text(
            "✅ Задание сохранено! Сделать ещё одно?",
            reply_markup=admin_yes_no_kb("more"),
        )
        return

    if action == "homework":
        text = context.user_data.get("hw_text", "")
        create_assignment("theory", {"text": text}, gid, is_homework=True)
        context.user_data.pop("hw_text", None)
        context.user_data["grp_pick_action"] = None
        await q.edit_message_text("✅ Домашнее задание выложено.", reply_markup=admin_menu_kb())
        return

    if action == "announce":
        ann_text = context.user_data.get("ann_text", "")
        when_text = context.user_data.get("ann_when", "")
        where_text = context.user_data.get("ann_where", "")
        create_announcement(ann_text, when_text, where_text, gid)
        for k in ("ann_text", "ann_when", "ann_where"):
            context.user_data.pop(k, None)
        context.user_data["grp_pick_action"] = None
        await q.edit_message_text("✅ Анонс опубликован.", reply_markup=admin_menu_kb())
        return

    if action == "assign_pending":
        uid = context.user_data.pop("pending_uid", None)
        if uid:
            set_user_group(uid, gid)
            try:
                await context.bot.send_message(
                    uid,
                    "Ты в группе! Открой меню через /start.",
                )
            except Exception:
                pass
        context.user_data["grp_pick_action"] = None
        await q.edit_message_text("✅ Ученик распределён.", reply_markup=admin_menu_kb())
        return

    if action == "move_student":
        uid = context.user_data.pop("move_uid", None)
        if uid:
            set_user_group(uid, gid)
        context.user_data["grp_pick_action"] = None
        await q.edit_message_text("✅ Ученик перемещён.", reply_markup=admin_menu_kb())
        return

    if action == "delete_group_pick":
        # выбранная группа для удаления задания
        rows = assignments_in_group(gid, homework=False) + assignments_in_group(gid, homework=True)
        if not rows:
            await q.edit_message_text("В этой группе нет заданий.", reply_markup=admin_menu_kb())
            return
        await q.edit_message_text(
            "Выбери задание для удаления:",
            reply_markup=assignments_kb(rows, delete=True),
        )
        return

    await q.edit_message_text("Неизвестное действие.", reply_markup=admin_menu_kb())


async def more_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["create_payload"] = {}
    context.user_data["create_is_hw"] = False
    await q.edit_message_text("Выберите тип задания:", reply_markup=admin_create_type_kb())


async def more_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Админ-панель:", reply_markup=admin_menu_kb())


# ---------------- УДАЛИТЬ ЗАДАНИЕ ----------------

async def admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    groups = list_groups()
    if not groups:
        await q.edit_message_text("Групп нет.", reply_markup=admin_back_kb())
        return
    context.user_data["grp_pick_action"] = "delete_group_pick"
    await q.edit_message_text("Выбери группу:", reply_markup=groups_pick_kb(groups))


async def asg_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    aid = int(q.data.replace("asg_del_", ""))
    delete_assignment(aid)
    await q.edit_message_text(f"✅ Задание #{aid} удалено.", reply_markup=admin_menu_kb())


# ---------------- РАССЫЛКА ----------------

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["state"] = ADM_BROADCAST
    await q.edit_message_text("Введите текст для рассылки всем ученикам:")


async def on_adm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["state"] = None
    ids = all_student_ids()
    sent, failed = 0, 0
    for uid in ids:
        try:
            await context.bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"✅ Отправлено: {sent}\n❌ Ошибок: {failed}",
        reply_markup=admin_menu_kb(),
    )


# ---------------- Д/З ----------------

async def admin_homework(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["state"] = ADM_HW_TEXT
    context.user_data["create_is_hw"] = True
    await q.edit_message_text("Введите текст домашнего задания:")


async def on_adm_hw_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["hw_text"] = update.message.text.strip()
    context.user_data["state"] = None
    await ask_group_for(update, context, action="homework")


# ---------------- АНОНС ONLINE ----------------

async def admin_online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["state"] = ADM_ANN_TEXT
    await q.edit_message_text("Введите название/описание онлайн-урока:")


async def on_adm_ann_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ann_text"] = update.message.text.strip()
    context.user_data["state"] = ADM_ANN_WHEN
    await update.message.reply_text("Когда? (например: 25.10 в 19:00 МСК)")


async def on_adm_ann_when(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ann_when"] = update.message.text.strip()
    context.user_data["state"] = ADM_ANN_WHERE
    await update.message.reply_text("Где? (ссылка или платформа)")


async def on_adm_ann_where(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ann_where"] = update.message.text.strip()
    context.user_data["state"] = None
    await ask_group_for(update, context, action="announce")


# ---------------- ГРУППЫ ----------------

async def admin_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    groups = list_groups()
    await q.edit_message_text(
        "Группы:",
        reply_markup=groups_kb_with_new(groups),
    )


async def grp_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["state"] = ADM_GROUP_NAME
    await q.edit_message_text("Введите название новой группы (например: F1):")


async def on_adm_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Введи название.")
        return
    get_or_create_group(name)
    context.user_data["state"] = None
    await update.message.reply_text("✅ Группа создана.", reply_markup=admin_menu_kb())


async def grp_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    gid = int(q.data.replace("grp_view_", ""))
    grp = get_group(gid)
    if not grp:
        await q.edit_message_text("Группа не найдена.", reply_markup=admin_back_kb())
        return
    students = list_students(gid)
    lines = [f"👥 Группа {grp[1]}:"]
    if not students:
        lines.append("— учеников нет")
    else:
        for uid, name, _g in students:
            lines.append(f"  • {name} (id {uid})")

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Добавить ученика", callback_data=f"grp_add_{gid}")],
        [InlineKeyboardButton("Назад", callback_data="admin_groups")],
    ])
    await q.edit_message_text("\n".join(lines), reply_markup=kb)


async def grp_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    gid = int(q.data.replace("grp_add_", ""))
    rows = students_not_in_group(gid)
    if not rows:
        await q.edit_message_text("Все ученики уже в этой группе.", reply_markup=admin_back_kb())
        return
    context.user_data["picking_for"] = "move"
    context.user_data["move_to_group"] = gid
    await q.edit_message_text(
        "Кого добавить в эту группу?",
        reply_markup=students_kb(rows),
    )


# ---------------- ЗАЯВКИ ----------------

async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = pending_students()
    if not rows:
        await q.edit_message_text("Заявок нет.", reply_markup=admin_back_kb())
        return
    context.user_data["picking_for"] = "pending"
    kb_rows = [(uid, name, None) for uid, name in rows]
    await q.edit_message_text("Заявки (без группы):", reply_markup=students_kb(kb_rows))


# ---------------- ВЫБОР УЧЕНИКА ----------------

async def stud_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = int(q.data.replace("stud_pick_", ""))
    action = context.user_data.get("picking_for")

    if action == "view":
        await admin_student_profile(update, context, uid)
        return

    if action == "grade":
        context.user_data["grade_target"] = uid
        context.user_data["picking_for"] = None
        await q.edit_message_text(
            "Выбери источник оценки:", reply_markup=admin_grade_source_kb()
        )
        return

    if action == "move":
        gid = context.user_data.pop("move_to_group", None)
        if gid is not None:
            set_user_group(uid, gid)
        context.user_data["picking_for"] = None
        await q.edit_message_text("✅ Ученик добавлен в группу.", reply_markup=admin_menu_kb())
        return

    if action == "pending":
        context.user_data["picking_for"] = None
        context.user_data["pending_uid"] = uid
        context.user_data["grp_pick_action"] = "assign_pending"
        groups = list_groups()
        if not groups:
            await q.edit_message_text(
                "Сначала создай группу (Меню → Группы → ➕).",
                reply_markup=admin_menu_kb(),
            )
            return
        await q.edit_message_text("В какую группу?", reply_markup=groups_pick_kb(groups))
        return

    await q.edit_message_text("Неизвестное действие.", reply_markup=admin_menu_kb())


# ---------------- выдача оценки из профиля ----------------

async def adm_give_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = int(q.data.replace("adm_give_", ""))
    context.user_data["grade_target"] = uid
    await q.edit_message_text("Выбери источник оценки:", reply_markup=admin_grade_source_kb())
