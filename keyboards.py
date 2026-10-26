from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from db import has_submission


def gender_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Мужской", callback_data="gender_m")],
        [InlineKeyboardButton("Женский", callback_data="gender_f")],
        [InlineKeyboardButton("Не бинарный", callback_data="gender_nb")],
        [InlineKeyboardButton("Не предпочитаю сообщать", callback_data="gender_na")],
    ])


def confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Да", callback_data="confirm_yes")],
    ])


def mode_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("С оценками (рекомендация)", callback_data="mode_grades")],
        [InlineKeyboardButton("Без оценок", callback_data="mode_no_grades")],
    ])


def student_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Задания", callback_data="menu_assignments")],
        [InlineKeyboardButton("Домашние задания", callback_data="menu_homework")],
        [InlineKeyboardButton("Онлайн урок", callback_data="menu_online")],
        [InlineKeyboardButton("Оценки", callback_data="menu_grades")],
        [InlineKeyboardButton("Профиль", callback_data="menu_profile")],
    ])


def back_to_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Назад", callback_data="back_menu")],
    ])


def admin_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Ученики", callback_data="admin_students")],
        [InlineKeyboardButton("Сделать задание", callback_data="admin_create")],
        [InlineKeyboardButton("Удалить задание", callback_data="admin_delete")],
        [InlineKeyboardButton("Разослать SMS", callback_data="admin_broadcast")],
        [InlineKeyboardButton("Поставить оценку", callback_data="admin_grade")],
        [InlineKeyboardButton("Выложить Д/З", callback_data="admin_homework")],
        [InlineKeyboardButton("Анонсировать online-урок", callback_data="admin_online")],
        [InlineKeyboardButton("Группы", callback_data="admin_groups")],
        [InlineKeyboardButton("Заявки (без группы)", callback_data="admin_pending")],
    ])


def admin_back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Назад", callback_data="admin_back")],
    ])


def admin_create_type_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Выбрать ответ", callback_data="ctype_choice")],
        [InlineKeyboardButton("Перевести", callback_data="ctype_translate")],
        [InlineKeyboardButton("Написать ответ", callback_data="ctype_write")],
        [InlineKeyboardButton("Теория", callback_data="ctype_theory")],
    ])


def admin_grade_source_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Занятие", callback_data="gsource_lesson")],
        [InlineKeyboardButton("Домашняя работа", callback_data="gsource_homework")],
        [InlineKeyboardButton("Видео-урок", callback_data="gsource_video")],
    ])


def admin_yes_no_kb(prefix: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Да", callback_data=f"{prefix}_yes"),
            InlineKeyboardButton("Нет", callback_data=f"{prefix}_no"),
        ],
    ])


def groups_kb(rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(name, callback_data=f"grp_view_{gid}")] for gid, name in rows
    ])


def groups_kb_with_new(rows):
    kb = [[InlineKeyboardButton(name, callback_data=f"grp_view_{gid}")] for gid, name in rows]
    kb.append([InlineKeyboardButton("➕ Новая группа", callback_data="grp_new")])
    return InlineKeyboardMarkup(kb)


def groups_pick_kb(rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(name, callback_data=f"grp_pick_{gid}")] for gid, name in rows
    ])


def students_kb(rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(name or f"id{uid}", callback_data=f"stud_pick_{uid}")]
        for uid, name, *_ in rows
    ])


def assignments_kb(rows, user_id=None, delete=False):
    kb = []
    for row in rows:
        aid, atype = row[0], row[1]
        if delete:
            label = f"🗑 #{aid} [{atype}]"
            cb = f"asg_del_{aid}"
        else:
            emoji = "📘" if atype == "theory" else "❓"
            status = ""
            if user_id:
                sub = has_submission(user_id, aid)
                if sub:
                    status = " ✅" if sub[0] else " ❌"
            label = f"{emoji} #{aid} [{atype}]{status}"
            cb = f"asg_open_{aid}"
        kb.append([InlineKeyboardButton(label, callback_data=cb)])
    return InlineKeyboardMarkup(kb)


def choices_kb(assignment_id, options):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(opt, callback_data=f"ans_choice_{assignment_id}_{i}")]
        for i, opt in enumerate(options)
    ])
