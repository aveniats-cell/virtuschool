import os
import logging

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)

from db import init_schema
import states
from handlers import student, admin


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("virtu")


# ---------------- текстовый роутер ----------------

TEXT_ROUTES = {
    states.ONB_NAME: student.onb_name,
    states.ONB_RATING: student.onb_rating,
    states.STU_ANSWER: student.ans_text,

    states.ADM_CREATE_Q: admin.on_adm_create_q,
    states.ADM_CREATE_OPTIONS: admin.on_adm_create_options,
    states.ADM_CREATE_CORRECT: admin.on_adm_create_correct,
    states.ADM_CREATE_ANSWER: admin.on_adm_create_answer,
    states.ADM_CREATE_THEORY: admin.on_adm_create_theory,

    states.ADM_GRADE: admin.on_adm_grade,
    states.ADM_BROADCAST: admin.on_adm_broadcast,
    states.ADM_HW_TEXT: admin.on_adm_hw_text,

    states.ADM_ANN_TEXT: admin.on_adm_ann_text,
    states.ADM_ANN_WHEN: admin.on_adm_ann_when,
    states.ADM_ANN_WHERE: admin.on_adm_ann_where,

    states.ADM_GROUP_NAME: admin.on_adm_group_name,
}


async def route_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    if not state:
        return
    handler = TEXT_ROUTES.get(state)
    if handler:
        await handler(update, context)


# ---------------- /cancel ----------------

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Отменено. /start — вернуться в меню.")


# ---------------- сборка ----------------

def build_app():
    init_schema()

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан")

    app = ApplicationBuilder().token(token).build()

    # команды
    app.add_handler(CommandHandler("start", student.start))
    app.add_handler(CommandHandler("admin", admin.admin_start))
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    # студент — онбординг
    app.add_handler(CallbackQueryHandler(student.onb_gender, pattern=r"^gender_"))
    app.add_handler(CallbackQueryHandler(student.onb_confirm, pattern=r"^confirm_yes$"))
    app.add_handler(CallbackQueryHandler(student.onb_mode, pattern=r"^mode_"))

    # меню студента
    app.add_handler(CallbackQueryHandler(student.menu_assignments, pattern=r"^menu_assignments$"))
    app.add_handler(CallbackQueryHandler(student.menu_homework, pattern=r"^menu_homework$"))
    app.add_handler(CallbackQueryHandler(student.menu_online, pattern=r"^menu_online$"))
    app.add_handler(CallbackQueryHandler(student.menu_grades, pattern=r"^menu_grades$"))
    app.add_handler(CallbackQueryHandler(student.menu_profile, pattern=r"^menu_profile$"))
    app.add_handler(CallbackQueryHandler(student.show_menu, pattern=r"^back_menu$"))

    # прохождение заданий
    app.add_handler(CallbackQueryHandler(student.open_assignment, pattern=r"^asg_open_"))
    app.add_handler(CallbackQueryHandler(student.ans_choice, pattern=r"^ans_choice_"))

    # админ — меню
    app.add_handler(CallbackQueryHandler(admin.back_to_admin, pattern=r"^admin_back$"))
    app.add_handler(CallbackQueryHandler(admin.admin_students, pattern=r"^admin_students$"))
    app.add_handler(CallbackQueryHandler(admin.admin_create, pattern=r"^admin_create$"))
    app.add_handler(CallbackQueryHandler(admin.admin_delete, pattern=r"^admin_delete$"))
    app.add_handler(CallbackQueryHandler(admin.admin_broadcast, pattern=r"^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin.admin_grade_entry, pattern=r"^admin_grade$"))
    app.add_handler(CallbackQueryHandler(admin.admin_homework, pattern=r"^admin_homework$"))
    app.add_handler(CallbackQueryHandler(admin.admin_online, pattern=r"^admin_online$"))
    app.add_handler(CallbackQueryHandler(admin.admin_groups, pattern=r"^admin_groups$"))
    app.add_handler(CallbackQueryHandler(admin.admin_pending, pattern=r"^admin_pending$"))

    # админ — создание
    app.add_handler(CallbackQueryHandler(admin.ctype_choice, pattern=r"^ctype_choice$"))
    app.add_handler(CallbackQueryHandler(admin.ctype_translate, pattern=r"^ctype_translate$"))
    app.add_handler(CallbackQueryHandler(admin.ctype_write, pattern=r"^ctype_write$"))
    app.add_handler(CallbackQueryHandler(admin.ctype_theory, pattern=r"^ctype_theory$"))
    app.add_handler(CallbackQueryHandler(admin.more_yes, pattern=r"^more_yes$"))
    app.add_handler(CallbackQueryHandler(admin.more_no, pattern=r"^more_no$"))

    # админ — оценка
    app.add_handler(CallbackQueryHandler(admin.admin_grade_source, pattern=r"^gsource_"))
    app.add_handler(CallbackQueryHandler(admin.adm_give_grade, pattern=r"^adm_give_"))

    # админ — группы
    app.add_handler(CallbackQueryHandler(admin.grp_new, pattern=r"^grp_new$"))
    app.add_handler(CallbackQueryHandler(admin.grp_view, pattern=r"^grp_view_"))
    app.add_handler(CallbackQueryHandler(admin.grp_add, pattern=r"^grp_add_"))
    app.add_handler(CallbackQueryHandler(admin.grp_pick, pattern=r"^grp_pick_"))

    # удаление задания
    app.add_handler(CallbackQueryHandler(admin.asg_del, pattern=r"^asg_del_"))

    # выбор ученика — единый роутер
    app.add_handler(CallbackQueryHandler(admin.stud_pick, pattern=r"^stud_pick_"))

    # текстовые сообщения — последними (после всех callback)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_text))

    return app


def main():
    app = build_app()
    log.info("Бот Virtù запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
