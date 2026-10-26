import json
from telegram import Update
from telegram.ext import ContextTypes

from db import (
    get_user, create_user, save_submission, has_submission,
    assignments_for_user, latest_homework, latest_announcement,
    weighted_avg, last_grades, done_count, get_assignment,
    set_user_group, user_is_admin, pending_students,
)
from keyboards import (
    gender_kb, confirm_kb, mode_kb, student_menu_kb, back_to_menu_kb,
    assignments_kb, choices_kb,
)
from states import ONB_NAME, ONB_RATING, STU_ANSWER
from utils import translate_matches, exact_matches


# ---------------- /start ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user

    if user_is_admin(tg_user):
        from handlers.admin import show_admin_menu
        await show_admin_menu(update, context)
        return

    user = get_user(tg_user.id)
    if user:
        await update.message.reply_text("Меню:", reply_markup=student_menu_kb())
        return

    context.user_data.clear()
    context.user_data["state"] = ONB_NAME
    await update.message.reply_text(
        "Привет! Я бот Virtù, помогу тебе с изучением итальянского языка.\n"
        "Как к тебе можно обращаться?"
    )


# ---------------- онбординг ----------------

async def onb_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Пожалуйста, введи имя.")
        return
    context.user_data["name"] = name
    context.user_data["state"] = None
    await update.message.reply_text("Какой у тебя пол?", reply_markup=gender_kb())


async def onb_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["gender"] = q.data.replace("gender_", "")
    context.user_data["state"] = ONB_RATING
    await q.edit_message_text(
        f"Хорошо, {context.user_data['name']}, как ты оцениваешь свои шансы "
        f"на изучение языка? (от 1 до 10)\nНапиши число."
    )


async def onb_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rating = int(update.message.text.strip())
        assert 1 <= rating <= 10
    except (ValueError, AssertionError):
        await update.message.reply_text("Пожалуйста, введи число от 1 до 10.")
        return

    context.user_data["self_rating"] = rating
    context.user_data["state"] = None
    name = context.user_data["name"]
    if rating <= 5:
        text = f"{name}, я уверен, у тебя всё получится. Ты готова?"
    else:
        text = "Отличный настрой! То что надо. Ну что, я так понимаю, ты готова?"
    await update.message.reply_text(text, reply_markup=confirm_kb())


async def onb_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        f"{context.user_data['name']}, пожалуйста, выбери режим обучения, "
        f"который тебе больше подходит.\n\n"
        f"В режиме с оценками есть возможность получить сертификат.",
        reply_markup=mode_kb(),
    )


async def onb_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    mode = "grades" if q.data == "mode_grades" else "no_grades"

    create_user(
        user_id=update.effective_user.id,
        name=context.user_data.get("name"),
        gender=context.user_data.get("gender"),
        self_rating=context.user_data.get("self_rating"),
        mode=mode,
    )

    from db import get_admin_id
    admin_id = get_admin_id()
    if admin_id:
        try:
            await context.bot.send_message(
                admin_id,
                f"📝 Новая заявка: {context.user_data.get('name')} "
                f"(id {update.effective_user.id})\n"
                f"Пол: {context.user_data.get('gender')}, "
                f"самооценка: {context.user_data.get('self_rating')}, "
                f"режим: {mode}\n\n"
                f"Распредели в группу через «Заявки» или «Группы».",
            )
        except Exception:
            pass

    context.user_data.clear()
    await q.edit_message_text(
        "Отлично! Заявка отправлена администратору. "
        "После распределения в группу откроется меню."
    )


# ---------------- главное меню ----------------

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = None
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Меню:", reply_markup=student_menu_kb())
    else:
        await update.message.reply_text("Меню:", reply_markup=student_menu_kb())


async def menu_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    user = get_user(uid)
    if not user:
        await q.edit_message_text("Профиль не найден. Используй /start.", reply_markup=back_to_menu_kb())
        return
    avg = weighted_avg(uid)
    avg_s = avg if avg is not None else "None"
    done = done_count(uid)
    text = (
        f"👤 Имя: {user[1]}\n"
        f"Пол: {user[2]}\n"
        f"Средневзвешенная оценка: {avg_s}\n"
        f"Выполнено заданий: {done}"
    )
    await q.edit_message_text(text, reply_markup=back_to_menu_kb())


async def menu_grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    avg = weighted_avg(uid)
    avg_s = avg if avg is not None else "None"
    rows = last_grades(uid, 10)
    lines = [f"📊 Средневзвешенный балл: {avg_s}\n"]
    if not rows:
        lines.append("Оценок пока нет.")
    else:
        src_ru = {"lesson": "занятие", "homework": "д/з", "video": "видео"}
        for value, comment, source, created in rows:
            lines.append(f"{value} — {comment or '—'} ({src_ru.get(source, source)}, {created})")
    await q.edit_message_text("\n".join(lines), reply_markup=back_to_menu_kb())


async def menu_assignments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    rows = assignments_for_user(uid, homework=False)
    if not rows:
        await q.edit_message_text("Заданий пока нет.", reply_markup=back_to_menu_kb())
        return
    await q.edit_message_text(
        "Выбери задание:",
        reply_markup=assignments_kb(rows, user_id=uid),
    )


async def menu_homework(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    hw = latest_homework(uid)
    if not hw:
        await q.edit_message_text("Свежих домашних заданий нет.", reply_markup=back_to_menu_kb())
        return
    await q.edit_message_text(
        "Свежее домашнее задание:",
        reply_markup=assignments_kb([hw], user_id=uid),
    )


async def menu_online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ann = latest_announcement(update.effective_user.id)
    if not ann:
        text = "Анонсов онлайн-урока пока нет."
    else:
        ann_text, when_text, where_text = ann
        text = f"🎥 {ann_text}\n\nКогда: {when_text}\nГде: {where_text}"
    await q.edit_message_text(text, reply_markup=back_to_menu_kb())


# ---------------- прохождение ----------------

async def open_assignment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    aid = int(q.data.replace("asg_open_", ""))
    asg = get_assignment(aid)
    if not asg:
        await q.edit_message_text("Задание не найдено.", reply_markup=back_to_menu_kb())
        return

    prev = has_submission(update.effective_user.id, aid)
    if prev:
        verdict = "✅ уже пройдено верно" if prev[0] else f"❌ уже пройдено неверно (твой ответ: {prev[1]})"
        await q.edit_message_text(
            f"Задание #{aid}: {verdict}. Повторно не требуется.",
            reply_markup=back_to_menu_kb(),
        )
        return

    atype = asg[1]
    payload = json.loads(asg[2])

    if atype == "theory":
        save_submission(update.effective_user.id, aid, "", True)
        await q.edit_message_text(
            f"📘 Теория #{aid}\n\n{payload.get('text', '')}",
            reply_markup=back_to_menu_kb(),
        )
        return

    if atype == "choice":
        await q.edit_message_text(
            f"❓ {payload.get('question', '')}",
            reply_markup=choices_kb(aid, payload.get("options", [])),
        )
        return

    if atype in ("translate", "write"):
        context.user_data["current_assignment"] = {"id": aid, "type": atype, "payload": payload}
        context.user_data["state"] = STU_ANSWER
        hint = "Переведи на русский / итальянский." if atype == "translate" else "Напиши ответ."
        await q.edit_message_text(
            f"✍️ {payload.get('question', '')}\n\n{hint} Просто отправь ответ сообщением."
        )
        return

    await q.edit_message_text("Неизвестный тип задания.", reply_markup=back_to_menu_kb())


async def ans_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    # ans_choice_<aid>_<idx>
    parts = q.data.split("_")
    aid = int(parts[2])
    idx = int(parts[3])

    asg = get_assignment(aid)
    if not asg:
        await q.edit_message_text("Задание не найдено.", reply_markup=back_to_menu_kb())
        return
    if has_submission(update.effective_user.id, aid):
        await q.edit_message_text("Уже пройдено.", reply_markup=back_to_menu_kb())
        return

    payload = json.loads(asg[2])
    options = payload.get("options", [])
    correct_idx = payload.get("correct_index", -1)
    picked = options[idx] if 0 <= idx < len(options) else "?"
    correct_text = options[correct_idx] if 0 <= correct_idx < len(options) else "?"

    ok = idx == correct_idx
    save_submission(update.effective_user.id, aid, picked, ok)

    await q.edit_message_text(
        (f"✅ Верно! Ответ: {correct_text}" if ok
         else f"❌ Неверно. Правильный ответ: {correct_text}"),
        reply_markup=back_to_menu_kb(),
    )


async def ans_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur = context.user_data.get("current_assignment")
    if not cur:
        context.user_data["state"] = None
        await update.message.reply_text("Нет активного задания.", reply_markup=student_menu_kb())
        return

    aid = cur["id"]
    atype = cur["type"]
    payload = cur["payload"]
    user_answer = update.message.text.strip()

    if has_submission(update.effective_user.id, aid):
        context.user_data.pop("current_assignment", None)
        context.user_data["state"] = None
        await update.message.reply_text("Уже пройдено.", reply_markup=student_menu_kb())
        return

    correct = payload.get("answer", "")
    ok = translate_matches(user_answer, correct) if atype == "translate" else exact_matches(user_answer, correct)

    save_submission(update.effective_user.id, aid, user_answer, ok)
    context.user_data.pop("current_assignment", None)
    context.user_data["state"] = None

    await update.message.reply_text(
        (f"✅ Верно!" if ok else f"❌ Неверно. Правильный ответ: {correct}"),
        reply_markup=student_menu_kb(),
    )
