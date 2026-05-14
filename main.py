#!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║   بوت حاسبة المعدل — Semestre 06        ║
║   Électrotechnique — Université Sétif   ║
╚══════════════════════════════════════════╝

الصيغ المستخدمة:
  Coeff 3 → Note = TD×0.2 + TP×0.2 + Examen×0.6
  Coeff 2 → Note = TD×0.4 + Examen×0.6
  Coeff 1 → Note = Examen فقط

التثبيت:
  pip install python-telegram-bot==20.7

التشغيل:
  python moyenne_bot.py
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

# ─── ضع توكنك هنا ────────────────────────────────────────────
import os
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# ──────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ═══════════════════════════════════════════════════════════════
#  تعريف المواد
# ═══════════════════════════════════════════════════════════════
MODULES = [
    {"name": "Matériaux en électrotechnique", "coff": 1, "id": "mat"},
    {"name": "Entrepreneuriat et management",  "coff": 1, "id": "ent"},
    {"name": "Réseaux Electriques",            "coff": 3, "id": "res"},
    {"name": "Systèmes asservis discrets",     "coff": 3, "id": "sys"},
    {"name": "Electronique de puissance 2",    "coff": 3, "id": "elp"},
    {"name": "Machines Electriques",           "coff": 3, "id": "mac"},
    {"name": "Schémas et appareillages",       "coff": 2, "id": "sch"},
    {"name": "Traitement de signal",           "coff": 2, "id": "tra"},
    {"name": "Stage en entreprise 1",          "coff": 1, "id": "sta"},
]

# states للمحادثة — كل مادة ليها state/states خاصة بها
# نبني قائمة ديناميكية للـ states
STATES = {}
state_counter = 0
for m in MODULES:
    if m["coff"] == 3:
        STATES[f"{m['id']}_TD"]    = state_counter; state_counter += 1
        STATES[f"{m['id']}_TP"]    = state_counter; state_counter += 1
        STATES[f"{m['id']}_EXAM"]  = state_counter; state_counter += 1
    elif m["coff"] == 2:
        STATES[f"{m['id']}_TD"]    = state_counter; state_counter += 1
        STATES[f"{m['id']}_EXAM"]  = state_counter; state_counter += 1
    else:
        STATES[f"{m['id']}_EXAM"]  = state_counter; state_counter += 1

CONFIRM = state_counter  # state التأكيد النهائي

# ═══════════════════════════════════════════════════════════════
#  دوال مساعدة
# ═══════════════════════════════════════════════════════════════

def calc_note(m: dict, notes: dict) -> float:
    """يحسب نوت المادة حسب الـ coeff."""
    mid = m["id"]
    if m["coff"] == 3:
        return notes[f"{mid}_TD"] * 0.2 + notes[f"{mid}_TP"] * 0.2 + notes[f"{mid}_EXAM"] * 0.6
    elif m["coff"] == 2:
        return notes[f"{mid}_TD"] * 0.4 + notes[f"{mid}_EXAM"] * 0.6
    else:
        return notes[f"{mid}_EXAM"]


def calc_moyenne(notes: dict) -> float:
    """يحسب المعدل العام."""
    total_pond = sum(calc_note(m, notes) * m["coff"] for m in MODULES)
    total_coff = sum(m["coff"] for m in MODULES)
    return total_pond / total_coff


def mention(moy: float) -> str:
    if moy >= 16: return "🏆 ممتاز — Très Bien"
    if moy >= 14: return "✨ جيد جداً — Bien"
    if moy >= 12: return "👍 جيد — Assez Bien"
    if moy >= 10: return "✅ مقبول — Passable"
    return "❌ راسب — Ajourné"


def validate_note(text: str):
    """يتحقق أن العلامة بين 0 و 20، يرجع float أو None."""
    try:
        v = float(text.replace(",", "."))
        if 0 <= v <= 20:
            return round(v, 2)
        return None
    except ValueError:
        return None


def build_state_sequence():
    """يبني قائمة مرتبة من (state_key, module, field_label)."""
    seq = []
    for m in MODULES:
        mid = m["id"]
        if m["coff"] == 3:
            seq.append((f"{mid}_TD",   m, "Note TD"))
            seq.append((f"{mid}_TP",   m, "Note TP"))
            seq.append((f"{mid}_EXAM", m, "Note Examen"))
        elif m["coff"] == 2:
            seq.append((f"{mid}_TD",   m, "Note TD"))
            seq.append((f"{mid}_EXAM", m, "Note Examen"))
        else:
            seq.append((f"{mid}_EXAM", m, "Note Examen"))
    return seq

STATE_SEQ = build_state_sequence()  # قائمة مرتبة ثابتة


def get_next_state_key(current_key: str):
    """يرجع مفتاح الـ state التالي أو None إذا انتهينا."""
    keys = [s[0] for s in STATE_SEQ]
    try:
        idx = keys.index(current_key)
        return keys[idx + 1] if idx + 1 < len(keys) else None
    except ValueError:
        return None


async def ask_field(update: Update, state_key: str):
    """يرسل سؤال للمستخدم عن حقل معين."""
    for sk, m, label in STATE_SEQ:
        if sk == state_key:
            coff_emoji = "🟢" if m["coff"] == 3 else "🔵" if m["coff"] == 2 else "⚪"
            formula = ""
            if m["coff"] == 3:
                formula = "\n_TD×0.2 + TP×0.2 + Examen×0.6_"
            elif m["coff"] == 2:
                formula = "\n_TD×0.4 + Examen×0.6_"

            text = (
                f"{coff_emoji} *{m['name']}*"
                f" `[Coeff {m['coff']}]`{formula}\n\n"
                f"📝 أدخل *{label}* \\(0 — 20\\):"
            )
            await update.message.reply_text(
                text,
                parse_mode="MarkdownV2",
                reply_markup=ReplyKeyboardRemove()
            )
            return
    # fallback
    await update.message.reply_text(f"أدخل العلامة (0–20):")


# ═══════════════════════════════════════════════════════════════
#  Handlers
# ═══════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية المحادثة."""
    context.user_data.clear()
    context.user_data["notes"] = {}

    await update.message.reply_text(
        "🎓 *أهلاً بك في حاسبة المعدل*\n"
        "Calculateur de Moyenne — Semestre 06\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ Électrotechnique — Université Sétif\n\n"
        "سنمر على كل المواد واحدة واحدة 📚\n"
        "أدخل /annuler في أي وقت للإلغاء\n\n"
        "هيا نبدأ! 🚀",
        parse_mode="Markdown"
    )

    # أول state
    first_key = STATE_SEQ[0][0]
    context.user_data["current_key"] = first_key
    await ask_field(update, first_key)
    return STATES[first_key]


async def handle_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يستقبل العلامة ويمشي للحقل التالي."""
    text = update.message.text.strip()
    current_key = context.user_data.get("current_key")

    val = validate_note(text)
    if val is None:
        await update.message.reply_text(
            "⚠️ علامة غير صحيحة\\!\n"
            "أدخل رقم بين *0* و *20* \\(مثلاً: `14\\.5`\\)",
            parse_mode="MarkdownV2"
        )
        return STATES[current_key]

    # حفظ العلامة
    context.user_data["notes"][current_key] = val

    # الحقل التالي
    next_key = get_next_state_key(current_key)

    if next_key is None:
        # انتهينا — نحسب المعدل
        return await show_results(update, context)

    context.user_data["current_key"] = next_key
    await ask_field(update, next_key)
    return STATES[next_key]


async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعرض النتائج الكاملة."""
    notes = context.user_data["notes"]
    moy = calc_moyenne(notes)

    lines = ["📊 *تفاصيل المواد:*\n━━━━━━━━━━━━━━━━━━━━━"]
    for m in MODULES:
        note = calc_note(m, notes)
        icon = "🔴" if note < 10 else "🟢"
        lines.append(f"{icon} {m['name']}\n   `Coeff {m['coff']}` → *{note:.2f}/20*")

    moy_icon = "🔴" if moy < 10 else "🟢"
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🎯 *المعدل العام:* {moy_icon} `{moy:.2f} / 20`")
    lines.append(f"📋 *الملاحظة:* {mention(moy)}")
    lines.append("\n_أرسل /start لحساب جديد_")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء المحادثة."""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ تم الإلغاء\.\nأرسل /start للبدء من جديد\.",
        parse_mode="MarkdownV2",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أرسل /start لبدء حساب المعدل 🎓"
    )


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

def main():
    if BOT_TOKEN == "ضع_توكنك_هنا":
        print("❌ خطأ: ضع توكن البوت في متغير BOT_TOKEN!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # بناء قائمة الـ states للـ ConversationHandler
    states_dict = {}
    for sk, m, label in STATE_SEQ:
        states_dict[STATES[sk]] = [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note)
        ]

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states=states_dict,
        fallbacks=[CommandHandler("annuler", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    print("✅ البوت يعمل... اضغط Ctrl+C للإيقاف")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
