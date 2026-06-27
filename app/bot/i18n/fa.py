"""
All user-facing Persian strings in one place.
No string may appear in handlers directly — always import from here.

Custom emoji: emoji_registry.json + emoji_ids.json (packs: EmojiStatus, tgmacicons, vector_icons_by_fStikBot, FlagsPack)
See docs/EMOJI.md — run: python3 scripts/sync_emoji_packs.py && python3 scripts/auto_map_emoji_registry.py --write
"""
from app.bot.utils.emoji import i, p

# ─── Common ──────────────────────────────────────────────────────────────────

# Plain text — emoji added by keyboards via icon= (Unicode only, never HTML)
BACK = "بازگشت"
BACK_DOUBLE = "بازگشت"
BACK_TO_MENU = "بازگشت به منوی اصلی"
HOME = "منوی اصلی"
CANCEL = "لغو"
CONFIRM = "تایید"
REJECT = "رد کردن"
CLOSE = f"{p('close')}بستن"
REFRESH = f"{p('refresh')}بروزرسانی"
COMING_SOON = f"{p('soon')}این بخش به‌زودی فعال می‌شود."

# ─── Bot profile (shown before START + in bot info) ───────────────────────────

# Telegram limit: 512 chars — plain Unicode in profile (no custom emoji API)
BOT_DESCRIPTION = (
    f"{p('globe')}{p('rocket')} به ان‌سی‌وی‌پی‌ان خوش اومدی؛ انتخاب حرفه‌ای برای اینترنت آزاد، سریع و بی‌دردسر!\n\n"
    f"{p('support')} پشتیبانی ۲۴ ساعته واقعاً کنارت هستیم\n"
    f"{p('gift')} تحویل فوری سرویس بلافاصله بعد از پرداخت\n"
    f"{p('wallet')} پرداخت آسان و ریالی (کارت‌به‌کارت)\n"
    f"{p('chart')} قیمت‌گذاری منصفانه و شفاف\n"
    f"{p('star')} مدیریت مصرف و سرعت عالی\n"
    f"{p('handshake')} ارتباط پایدار و بدون قطعی\n\n"
    f"{p('wave')} برای شروع کافیست /start را ارسال کنی!"
)

BOT_SHORT_DESCRIPTION = (
    f"{p('globe')}{p('rocket')} ان‌سی‌ وی‌پی‌ان پرسرعت — تحویل آنی | پرداخت ریالی | پشتیبانی 24/7 {p('handshake')}"
)

# ─── Welcome & Main Menu ─────────────────────────────────────────────────────

CHANNEL_GATE_TEXT = (
    f"{p('lock')}<b>عضویت در کانال الزامی است</b>\n\n"
    "برای استفاده از خدمات ربات، ابتدا باید عضو کانال رسمی ما شوید.\n\n"
    "۱. روی دکمه کانال بزنید و Join را بزنید\n"
    "۲. پس از عضویت، «بررسی عضویت» را بزنید"
)
CHANNEL_GATE_VERIFY_BTN = "بررسی عضویت"
CHANNEL_GATE_VERIFY_FAILED = (
    "عضویت شما تأیید نشد.\n"
    "لطفاً در کانال عضو شوید و دوباره «بررسی عضویت» را بزنید."
)
CHANNEL_GATE_NOT_JOINED = (
    "هنوز عضو کانال نشده‌اید.\n\n"
    "لطفاً ابتدا در کانال عضو شوید، سپس «بررسی عضویت» را بزنید.\n\n"
    "کانال: {channels}"
)

WELCOME = (
    f"خوش اومدی به <b>ان‌سی‌وی‌پی‌ان</b>! {i('wave')}\n\n"
    f"{p('globe')}اینجا می‌تونی VPN پرسرعت و پایدار بگیری\n"
    f"{p('bolt')}اتصال سریع و بدون قطعی، مجهز به پروتکل‌های مدرن\n"
    f"{p('handshake')}پشتیبانی 24 ساعته در کنارت هستیم\n\n"
    "از گزینه‌های زیر یکی رو انتخاب کن:"
)

# Home menu — plain labels; icons from emoji_registry via keyboards (vector + Unicode fallback)
MAIN_BTN_BUY = "خرید سرویس"
MAIN_BTN_CONFIGS = "مدیریت کانفیگ‌ها"
MAIN_BTN_BALANCE = "افزایش موجودی"
MAIN_BTN_ACCOUNT = "حساب کاربری"
MAIN_BTN_FREE = "کانفیگ رایگان"
MAIN_BTN_SUPPORT = "ارتباط با پشتیبانی"
MAIN_BTN_APPS = "دریافت اپلیکیشن‌ها"
MAIN_BTN_ADMIN = "پنل مدیریت"

CMD_START = "منوی اصلی"
CMD_BUY = "خرید سرویس"
CMD_CONFIGS = "مدیریت کانفیگ‌ها"
CMD_TOPUP = "افزایش موجودی"

# ─── Errors ──────────────────────────────────────────────────────────────────

ERRORS = {
    "general": f"{p('error')}خطایی رخ داد. لطفاً مجدداً تلاش کنید.",
    "api_error": f"{p('warning')}خطا در ارتباط با سرور. لطفاً چند لحظه دیگر تلاش کنید.",
    "config_create_failed": (
        f"{p('error')}خطا در ایجاد سرویس. تیم پشتیبانی در حال بررسی است."
    ),
    "vpn_unavailable": (
        f"{p('error')}اتصال به پنل VPN برقرار نیست.\n"
        "لطفاً چند دقیقه بعد دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
    ),
    "insufficient_balance": (
        f"{p('wallet')}موجودی کافی نیست!\n\n"
        "موجودی فعلی: <b>{balance}</b> تومان\n"
        "مبلغ مورد نیاز: <b>{required}</b> تومان\n"
        "کمبود: <b>{shortage}</b> تومان\n\n"
        "برای افزایش موجودی از منوی اصلی اقدام کنید."
    ),
    "insufficient_balance_alert": (
        "موجودی کافی نیست!\n\n"
        "موجودی فعلی: {balance} تومان\n"
        "مبلغ مورد نیاز: {required} تومان\n"
        "کمبود: {shortage} تومان\n\n"
        "برای افزایش موجودی از منوی اصلی اقدام کنید."
    ),
    "service_name_taken": (
        f"{p('error')}این نام قبلاً استفاده شده است.\n"
        "نام دیگری انتخاب کنید."
    ),
    "service_name_invalid": (
        f"{p('error')}نام نامعتبر است!\n"
        "فقط حروف کوچک انگلیسی (a-z) و اعداد (0-9) مجاز است.\n"
        "طول نام باید بین 3 تا 30 کاراکتر باشد.\n\n"
        "دوباره تلاش کنید:"
    ),
    "invalid_discount": f"{p('error')}کد تخفیف نامعتبر یا منقضی شده است.",
    "discount_used": f"{p('error')}سقف استفاده شما از این کد تخفیف تکمیل شده است.",
    "banned": (
        f"{p('ban')}دسترسی شما محدود شده است.\n"
        "برای پیگیری با پشتیبانی تماس بگیرید."
    ),
    "admin_only": f"{p('ban')}این بخش فقط برای مدیران قابل دسترسی است.",
    "not_found": f"{p('error')}مورد درخواستی یافت نشد.",
    "config_not_found": f"{p('error')}سرویس مورد نظر یافت نشد.",
    "quantity_invalid": (
        f"{p('error')}تعداد نامعتبر است. عددی بین {{min}} تا {{max}} وارد کنید."
    ),
    "amount_invalid": f"{p('error')}مبلغ نامعتبر است. عدد صحیح وارد کنید.",
    "amount_min": f"{p('error')}حداقل مبلغ {{min}} تومان است.",
    "amount_max": f"{p('error')}حداکثر مبلغ {{max}} تومان است.",
}

# ─── Buy: type ───────────────────────────────────────────────────────────────

BUY_TYPE_HEADER = f"{p('cart')}برای خرید سرویس لطفاً یکی از دسته‌بندی‌های زیر را انتخاب کنید."

BUY_VIP_BTN = "سرویس VIP چند لوکیشن"

VIP_TIER_NAME_DEFAULT = "سرویس VIP چند لوکیشن"
VIP_PLANS_TABLE_SUBTITLE_DEFAULT = "یک اشتراک — همه سرورها فعال می‌شوند:"

VIP_PLAN_BTN = "{lead}{gb} گیگ · {price} تومان{badge}"

# ─── Buy: quantity ───────────────────────────────────────────────────────────

QUANTITY_PROMPT = (
    f"{p('package')}<b>تعداد سرویس</b>\n\n"
    f"{p('note')}پلن انتخابی: {{gb}} گیگ | {{days}} روزه | {{price}} ت\n"
    f"{p('wallet')}هر عدد: <b>{{price}} تومان</b>\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "چند تا می‌خوای؟\n"
    "بین <b>1</b> تا <b>{max}</b> عدد رو تایپ کن و بفرست:"
)

# ─── Buy: service name ───────────────────────────────────────────────────────

SERVICE_NAME_PROMPT = (
    f"{p('tag')}<b>نام سرویس</b>\n\n"
    "یه اسم دلخواه برای سرویست بنویس.\n"
    "فقط حروف انگلیسی کوچک و عدد مجازه.\n\n"
    f"{p('edit')}نمونه: <code>ali</code> یا <code>myVPN1</code>\n\n"
    "یا «نام رندوم» رو بزن تا خودمون یه اسم بسازیم."
)
SERVICE_NAME_RANDOM_BTN = "نام رندوم"

SERVICE_NAME_MULTI_PROMPT = (
    f"{p('tag')}<b>نام سرویس‌ها</b>\n\n"
    "{n} سرویس انتخاب کردی.\n"
    "یه نام پایه بنویس — شماره به انتهاش اضافه می‌شه.\n\n"
    f"{p('edit')}نمونه: <code>vpn</code> ← vpn-1، vpn-2 …\n\n"
    "یا «نام رندوم» رو بزن."
)

# ─── Buy: discount ───────────────────────────────────────────────────────────

DISCOUNT_PROMPT = (
    f"{p('ticket')}<b>کد تخفیف</b>\n\n"
    f"{p('package')}تعداد: <b>{{quantity}}</b> عدد\n"
    f"{p('money')}مبلغ قابل پرداخت: <b>{{amount}}</b> تومان\n\n"
    f"آیا کد تخفیف دارید؟ {p('gift')}"
)
DISCOUNT_HAVE_BTN = "کد تخفیف دارم"
DISCOUNT_NONE_BTN = "کد تخفیف ندارم"
DISCOUNT_ENTER_PROMPT = (
    f"{p('key')}<b>وارد کردن کد تخفیف</b>\n\n"
    f"{p('money')}مبلغ: <b>{{amount}}</b> تومان\n\n"
    f"کد تخفیف خود را تایپ کرده و ارسال کنید:"
)

DISCOUNT_APPLIED = (
    f"{p('confirm')}کد تخفیف اعمال شد!\n"
    f"{p('wallet')}تخفیف: <b>{{discount}}</b> تومان\n"
    f"{p('money')}مبلغ جدید: <b>{{new_amount}}</b> تومان"
)

# ─── Buy: payment method ─────────────────────────────────────────────────────

PAYMENT_METHOD_HEADER = (
    f"{p('refresh')}تحویل آنی | {{gb}} گیگ | {{days}} روزه | {{unit_price}} ت\n"
    f"{p('package')}تعداد: <b>{{quantity}}</b> عدد\n"
    f"{p('money')}مبلغ قابل پرداخت: <b>{{amount}}</b> تومان\n\n"
    "روش پرداخت را انتخاب کنید:\n"
    "<i>موجودی کیف پول شما روی دکمه نمایش داده می‌شود.</i>"
)
PAY_WALLET_BTN = "پرداخت از موجودی ({balance} ت)"
PAY_CARD_BTN = "کارت‌به‌کارت"

# ─── Buy: card payment ───────────────────────────────────────────────────────

CARD_PAYMENT = (
    f"{p('card')}<b>کارت به کارت</b>\n\n"
    f"{p('bank')}{{bank}}\n"
    f"{p('user')}{{owner}}\n"
    f"{p('card')}<code>{{card}}</code>\n\n"
    "──────────────────\n\n"
    f"{p('money')}مبلغ قابل پرداخت\n"
    "<b>{amount}</b> تومان\n\n"
    "──────────────────\n\n"
    f"{p('warning')}حتماً مبلغ را به همین مقدار واریز نمایید.\n"
    "در صورت واریز مبلغ غیر دقیق، مسئولیت تایید نشدن\n"
    "رسید بر عهده خود شما خواهد بود.\n\n"
    f"{p('camera')}پس از واریز، تصویر رسید را ارسال کنید.\n\n"
    f"{p('down')}برای کپی مبلغ یا شماره کارت، دکمه‌های زیر را بزنید."
)
COPY_RIAL_BTN = "مبلغ ریال"
COPY_TOMAN_BTN = "مبلغ تومان"
COPY_CARD_BTN = "شماره کارت"
CANCEL_PLAIN = "لغو"

RECEIPT_RECEIVED = (
    f"{p('confirm')}رسید پرداخت دریافت شد!\n\n"
    f"{p('pending')}در حال بررسی توسط تیم پشتیبانی…\n"
    "معمولاً در کمتر از 30 دقیقه تایید می‌شود.\n\n"
    "پس از تایید، سرویس شما فعال و اطلاع‌رسانی می‌شود."
)
RECEIPT_PROMPT = f"{p('camera')}لطفاً تصویر رسید پرداخت را ارسال کنید."

# ─── Buy: success ────────────────────────────────────────────────────────────

SERVICE_ACTIVATED_CAPTION = (
    f"{p('party')}<b>سرویس شما فعال شد!</b>\n\n"
    "━━━━━━━━━━━━━━━━\n"
    f"{p('tag')}<b>نام سرویس:</b> <code>{{name}}</code>\n"
    f"{p('package')}<b>پلن:</b> {{plan_name}} — {{gb}} گیگ | {{days}} روز\n"
    f"{p('clock')}<b>وضعیت:</b> {{expiry}}\n"
    "━━━━━━━━━━━━━━━━\n\n"
    f"{p('phone')}QR کد را اسکن کنید یا لینک را کپی کنید:\n"
    "<code>{sub_url}</code>\n\n"
    f"{p('info')}لینک را در برنامه VPN وارد کنید تا همه لوکیشن‌ها و سرورها خودکار اضافه شوند."
)
SERVICE_ACTIVATED_COPY_BTN = "کپی لینک اشتراک"
SERVICE_ACTIVATED_OPEN_BTN = "باز کردن لینک"
PURCHASE_SUCCESS_ONE = SERVICE_ACTIVATED_CAPTION
PURCHASE_SUCCESS_BULK = (
    f"{p('party')}<b>{{n}} سرویس با موفقیت ایجاد شد!</b>\n\n"
    "{lines}\n\n"
    "از منوی اصلی → «مدیریت کانفیگ‌ها» جزئیات هر سرویس را ببینید."
)
PURCHASE_LINE = f"{p('tag')}<b>{{name}}</b> — {{sub_url}}"
PURCHASE_REJECTED = (
    f"{p('error')}<b>پرداخت شما رد شد.</b>\n\n"
    "{reason}\n\n"
    "در صورت نیاز با پشتیبانی تماس بگیرید."
)

# ─── Admin payment forward ───────────────────────────────────────────────────

ADMIN_PAYMENT_FWD = (
    f"{p('card')}<b>درخواست پرداخت جدید</b>  #TXN-{{tx_id}}\n\n"
    f"{p('user')}کاربر: {{name}} (@{{username}})\n"
    f"{p('id_badge')}آیدی: <code>{{tg_id}}</code>\n"
    f"{p('package')}پلن: {{plan_name}}\n"
    f"{p('chart')}تعداد: {{quantity}}\n"
    f"{p('tag')}نام سرویس: <b>{{service_name}}</b>\n"
    f"{p('wallet')}مبلغ: <b>{{amount}}</b> تومان\n"
    f"{p('ticket')}تخفیف: {{discount}}\n"
    f"{p('clock')}زمان: {{datetime}}"
)
ADMIN_WALLET_FWD = (
    f"{p('wallet')}<b>درخواست شارژ کیف پول</b>  #TXN-{{tx_id}}\n\n"
    f"{p('user')}کاربر: {{name}} (@{{username}})\n"
    f"{p('id_badge')}آیدی: <code>{{tg_id}}</code>\n"
    f"{p('cash')}مبلغ: <b>{{amount}}</b> تومان\n"
    f"{p('clock')}زمان: {{datetime}}"
)
ADMIN_APPROVE_BTN = "تایید و ایجاد سرویس"
ADMIN_APPROVE_WALLET_BTN = "تایید شارژ"
ADMIN_REJECT_BTN = "رد کردن"
ADMIN_TX_PROCESSED_SHORT = (
    "{icon}<b>درخواست #{tx_id} {action_label}</b>\n\n"
    f"{p('user')}توسط: {{admin_name}} ({{admin_ref}})\n"
    f"{p('clock')}{{processed_at}}"
)
ADMIN_TX_PROCESSED_SUPER_FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━\n"
    "{icon}<b>{action_label}</b>\n"
    f"{p('user')}مدیر: {{admin_name}} ({{admin_ref}})\n"
    f"{p('id_badge')}آیدی مدیر: <code>{{admin_tg_id}}</code>\n"
    f"{p('clock')}{{processed_at}}"
)

# ─── Manage Configs ──────────────────────────────────────────────────────────

CONFIGS_LIST_HEADER = (
    f"{p('chart')}<b>مدیریت کانفیگ‌ها</b>\n\n"
    "تعداد: {count}"
)
CONFIGS_LIST_EMPTY = (
    f"{p('chart')}<b>مدیریت کانفیگ‌ها</b>\n\n"
    f"{p('error')}شما هیچ سرویس فعالی ندارید.\n\n"
    "برای خرید سرویس از منوی اصلی اقدام کنید."
)
CONFIG_LIST_ROW = "… {name}"
CONFIG_LIST_ROW_EXPIRED = f"{p('sleep')}{{name}} (منقضی)"

CONFIG_DETAIL = (
    f"{p('refresh')}نام سرویس: <b>{{name}}</b>\n"
    f"{p('star')}نوع سرویس: {{plan_name}}\n"
    f"{p('battery')}حجم: <b>{{total_gb}}</b> گیگ\n"
    f"{p('clock')}مدت زمان: {{duration}}\n"
    f"{p('user')}تعداد کاربر: نامحدود\n\n"
    f"{p('key')}<b>کانفیگ اتصال:</b>\n"
    "<code>{vless}</code>\n\n"
    f"{p('link')}<b>لینک اشتراک:</b>\n"
    "<code>{sub_url}</code>"
)

CONFIG_BTN_USAGE = "وضعیت سرویس"
CONFIG_BTN_GET_CONFIGS = "دریافت کانفیگ‌ها"
CONFIG_BTN_GET_SUB = "دریافت اشتراک"
CONFIG_BTN_DISABLE = "غیرفعال‌سازی موقت"
CONFIG_BTN_ENABLE = "فعال‌سازی"
CONFIG_BTN_DELETE = "حذف کانفیگ"
CONFIG_BTN_RESET_SUB = "تغییر لینک ساب"
CONFIG_BTN_QR = "ساب QR"
CONFIG_BTN_COPY_SUB = "کپی لینک اشتراک"
CONFIG_BTN_RENEW = "تمدید سرویس ({discount_pct}٪ تخفیف)"

RENEW_PLANS_HEADER = (
    f"{p('refresh')}<b>تمدید سرویس: {{name}}</b>\n\n"
    f"{p('gift')}<b>تخفیف تمدید: {{discount_pct}}٪</b> (خودکار — بدون کد)\n"
    "همان لینک اشتراک حفظ می‌شود.\n\n"
    f"{p('info')}با تمدید:\n"
    f"• <b>حجم پلن به سرویس اضافه می‌شود</b>\n"
    f"• <b>مهلت {{max_days}} روز</b> پس از اولین اتصال (شمارش از اولین استفاده)\n\n"
    "یک پلن (حجم) انتخاب کنید:"
)
RENEW_PLAN_BTN = "{lead}+ {gb} گیگ — {price} (قبل: {was_price})"
RENEW_PAYMENT_HEADER = (
    f"{p('refresh')}<b>تمدید {{name}}</b>\n\n"
    f"{p('battery')}حجم اضافه: <b>+{{gb}} گیگ</b>\n"
    f"{p('clock')}مهلت: <b>{{max_days}} روز</b> پس از اولین اتصال\n"
    f"{p('ticket')}تخفیف تمدید {{discount_pct}}٪: <b>-{{discount}}</b> ت\n"
    f"{p('wallet')}مبلغ نهایی: <b>{{amount}}</b> ت\n\n"
    "روش پرداخت را انتخاب کنید:"
)
RENEW_SUCCESS = (
    f"{p('confirm')}<b>سرویس «{{name}}» تمدید شد!</b>\n\n"
    f"{p('battery')}حجم شما <b>+{{gb}} گیگ</b> افزایش یافت.\n"
    f"{p('clock')}مهلت: <b>{{max_days}} روز</b> پس از اولین اتصال (تازه‌سازی)\n"
    f"{p('info')}{{expiry_note}}\n\n"
    f"{p('link')}لینک اشتراک <b>تغییر نکرده</b> — همان لینک قبلی را در اپ استفاده کنید.\n"
    "<code>{sub_url}</code>"
)
RENEW_WAIT = f"{p('pending')}در حال تمدید سرویس…"
TX_DESC_RENEW = "تمدید {plan_name} ({name})"
RENEW_REJECTED = (
    f"{p('error')}<b>درخواست تمدید رد شد.</b>\n\n"
    "{reason}\n\n"
    "در صورت نیاز با پشتیبانی تماس بگیرید."
)

ADMIN_RENEW_FWD = (
    f"{p('refresh')}<b>درخواست تمدید سرویس</b>  #TXN-{{tx_id}}\n\n"
    f"{p('user')}کاربر: {{name}} (@{{username}})\n"
    f"{p('id_badge')}آیدی: <code>{{tg_id}}</code>\n"
    f"{p('package')}پلن: {{plan_name}}\n"
    f"{p('tag')}سرویس: <b>{{service_name}}</b>\n"
    f"{p('wallet')}مبلغ: <b>{{amount}}</b> تومان\n"
    f"{p('ticket')}تخفیف تمدید: {{discount}}\n"
    f"{p('clock')}زمان: {{datetime}}"
)
ADMIN_APPROVE_RENEW_BTN = "تایید تمدید"

CONFIG_INFO_TRAFFIC = f"{p('battery')}{{used}} از {{total}} گیگ"
CONFIG_INFO_UNLIMITED = f"{p('infinity')}نامحدود"

CONFIG_STATUS_TEXT = (
    f"{p('chart')}<b>وضعیت سرویس: {{name}}</b>\n\n"
    f"{p('up')}مصرف حجم:\n"
    "<code>[{bar}] {used_gb} از {total_gb} گیگ ({pct}٪)</code>\n\n"
    f"{p('clock')}وضعیت انقضا: <b>{{expiry}}</b>\n"
    f"{p('pending')}روزهای باقیمانده: <b>{{days}}</b>\n\n"
    f"{p('up')}آپلود: {{up}}\n"
    f"{p('down')}دانلود: {{down}}"
)

CONFIG_GET_CONFIGS_TEXT = (
    f"{p('copy')}<b>کانفیگ‌های سرویس: {{name}}</b>\n"
    "<i>همه لوکیشن‌ها — پس از import اشتراک، همه را خواهید داشت</i>\n\n"
    "{links}"
)
CONFIG_GET_CONFIGS_EMPTY = (
    f"{p('error')}کانفیگی از پنل دریافت نشد. از لینک اشتراک استفاده کنید."
)
CONFIG_GET_SUB_TEXT = (
    f"{p('key')}<b>لینک اشتراک سرویس: {{name}}</b>\n\n"
    "<code>{url}</code>\n\n"
    "این لینک را در اپ خود وارد کنید.\n"
    f"{p('warning')}لینک اشتراک خصوصی است — با دیگران به اشتراک نگذارید."
)
DELAYED_START_FMT = f"{p('pending')}هنوز شروع نشده — شروع {{n}} روز پس از اولین اتصال"
CONFIG_NOT_STARTED = f"{p('pending')}هنوز شروع نشده"

CONFIG_DISABLED = f"{p('pause')}سرویس موقتاً غیرفعال شد."
CONFIG_ENABLED = f"{p('play')}سرویس مجدداً فعال شد."
CONFIG_RESET_SUB_DONE = (
    f"{p('refresh')}<b>لینک اشتراک جدید صادر شد</b>\n\n"
    "<code>{url}</code>\n\n"
    f"{p('info')}لینک قبلی دیگر کار نمی‌کند. در Hiddify یا v2box دوباره Import کنید."
)
CONFIG_QR_CAPTION = f"{p('link')}QR اشتراک: <b>{{name}}</b>"

CONFIG_DELETE_CONFIRM = (
    f"{p('warning')}<b>آیا مطمئن هستید؟</b>\n\n"
    "سرویس «<b>{name}</b>» برای همیشه حذف خواهد شد.\n"
    "این عمل قابل بازگشت نیست."
)
CONFIG_DELETE_YES = "بله، حذف شود"
CONFIG_DELETE_NO = "خیر، بازگشت"
CONFIG_DELETED = (
    f"{p('trash')}سرویس «{{name}}» حذف شد.\n\n"
    "اگر در v2Box هنوز کانفیگ می‌بینید، اشتراک قدیمی را از اپ حذف کنید."
)

# ─── Account / Wallet ────────────────────────────────────────────────────────

PROFILE_TEXT = (
    f"{p('user')}<b>پروفایل کاربری</b>\n\n"
    f"{p('user')}نام: <b>{{name}}</b>\n"
    f"{p('key')}نام کاربری: {{username}}\n"
    f"{p('id_badge')}آیدی: <code>{{tg_id}}</code>\n"
    f"{p('money')}موجودی: <b>{{balance}}</b> تومان"
)
WALLET_TOPUP_BTN = "افزایش موجودی"
WALLET_TX_BTN = "تراکنش‌های من"

TOPUP_AMOUNTS_HEADER = (
    f"{p('wallet')}<b>افزایش موجودی کیف پول</b>\n\n"
    "مبلغ موردنظر را انتخاب یا وارد کنید:"
)
TOPUP_CUSTOM_BTN = "مبلغ دلخواه"
TOPUP_CUSTOM_PROMPT = (
    f"{p('edit')}مبلغ مورد نظر را به تومان وارد کنید:\n"
    "(مثال: 100000)"
)

TX_LIST_HEADER = f"{p('receipt')}<b>تراکنش‌های من</b>\n"
TX_LIST_EMPTY = f"{p('receipt')}<b>تراکنش‌های من</b>\n\nهنوز تراکنشی ثبت نشده است."
TX_LIST_ROW = (
    "──────────────────\n"
    "{icon} {desc}\n"
    f"{p('wallet')}{{sign}}{{amount}} تومان\n"
    f"{p('clock')}{{date}}"
)
TX_ICON_CREDIT = i("confirm")
TX_ICON_DEBIT = i("error")
TX_ICON_PENDING = i("pending")
TX_ICON_REFERRAL = i("gift")

WALLET_CHARGED = (
    f"{p('confirm')}<b>موجودی شما با موفقیت شارژ شد!</b>\n\n"
    "موجودی جدید: <b>{balance}</b> تومان"
)

# ─── Referral / Free Config ──────────────────────────────────────────────────

REFERRAL_WITH_STATS = (
    f"{p('referral')}<b>دعوت دوستان — ان‌سی‌ وی‌پی‌ان</b>\n\n"
    "با دعوت از دوستان خود و ثبت خرید توسط آن‌ها با لینک اختصاصی‌تان:\n"
    f"{p('wallet')}<b>{{ref_bonus}} تومان</b> به کیف پول شما اضافه می‌شود\n"
    f"{p('gift')}دوستتان نیز <b>{{friend_bonus}} تومان</b> هدیه‌ی اولیه دریافت می‌کند\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    f"{p('chart')}<b>وضعیت شما:</b>\n"
    f"{p('user')}تعداد دعوت‌شده‌ها: <b>{{count}}</b> نفر\n"
    f"{p('cart')}مجموع خریدها: <b>{{purchases}}</b> بار\n"
    f"{p('wallet')}کل پاداش دریافتی: <b>{{total_revenue}}</b> تومان\n\n"
    f"{p('link')}<b>لینک ویژه شما:</b>\n"
    "<code>{ref_link}</code>"
)
REFERRAL_NO_STATS = (
    f"{p('referral')}<b>دوستت رو دعوت کن، هر دو سود می‌برید!</b>\n\n"
    "هر بار که یه نفر با لینک تو بیاد و سرویس بخره،\n"
    f"<b>50,000 تومان</b> به کیف پولت واریز می‌شه. {p('cash')}\n\n"
    f"دوستت هم یه هدیه خوش‌آمد دریافت می‌کنه\n"
    f"تا از همون اول بتونه سرویس بگیره. {p('gift')}\n\n"
    f"{p('link')}<b>لینک دعوت اختصاصی:</b>\n"
    "<code>{ref_link}</code>"
)
REFERRAL_SHARE_BTN = "اشتراک‌گذاری لینک"
REFERRAL_POST_BTN = "متن آماده برای فوروارد"
REFERRAL_SHARE_DIALOG_TEXT = f"{p('bolt')}VPN پرسرعت — ان‌سی‌ وی‌پی‌ان"

REFERRAL_READY_POST = (
    f"<b>{p('bolt')}ان‌سی‌ وی‌پی‌ان — VPN سریع و ایمن</b>\n\n"
    f"پروتکل‌های مدرن VLESS {p('globe')}\n"
    f"پشتیبانی آنلاین {p('handshake')}\n"
    f"سازگار با تمامی دستگاه‌ها و اپراتورها {p('phone')}\n"
    f"بدون محدودیت تعداد دستگاه {p('lock')}\n\n"
    "با استفاده از لینک من عضو شو و هدیه‌ی خوش‌آمد بگیر:\n"
    "{ref_link}"
)
REFERRAL_READY_POST_HINT = f"{p('confirm')}متن آماده‌ست، می‌تونی فوروارد کنی."
REFERRAL_READY_POST_HINT_WITH_IMAGE = (
    f"{p('confirm')}عکس و متن آماده‌ست، می‌تونی فوروارد کنی."
)

# ─── Apps ────────────────────────────────────────────────────────────────────

APPS_HEADER = (
    f"{p('download')}<b>دریافت اپلیکیشن‌ها</b>\n\n"
    "سیستم‌عامل خود را انتخاب کنید:"
)
APPS_OS_BTN = {
    "android": "Android",
    "ios": "iOS",
    "windows": "Windows",
    "mac": "Mac",
    "linux": "Linux",
}
APPS_OS_HEADER = f"{p('download')}<b>اپلیکیشن‌های {{os}}</b>\n\nبرنامه مورد نظر را انتخاب کنید:"

# ─── Support ─────────────────────────────────────────────────────────────────

SUPPORT_HEADER = (
    f"{p('support')}<b>پشتیبانی ان‌سی‌ وی‌پی‌ان</b>\n\n"
    "سوالات متداول رو اول بررسی کن —\n"
    f"پاسخ خیلی از مشکلاتت رو اونجا پیدا می‌کنی {p('down')}"
)
SUPPORT_FAQ_BTN = "سوالات متداول (FAQ)"
SUPPORT_ONLINE_BTN = "چت با پشتیبانی"

FAQ_TEXT = (
    f"{p('faq')}<b>سوالات متداول — ان‌سی‌ وی‌پی‌ان</b>\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    f"{p('info')}<b>۱. آیا امکان استفاده آزمایشی وجود دارد؟</b>\n"
    "خیر، به دلایل امنیتی و پیشگیری از سوء استفاده، ما سرویس رایگان یا آزمایشی ارائه نمی‌کنیم.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    f"{p('info')}<b>۲. آیا برای تعداد کاربر یا دستگاه محدودیتی تعیین شده؟</b>\n"
    "خیر، هیچ گونه محدودیتی در تعداد دستگاه یا استفاده همزمان وجود ندارد و می‌توانید روی هر تعداد دستگاه دلخواه سرویس را فعال کنید.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    f"{p('info')}<b>۳. اتصال از لحاظ سرعت و پایداری چگونه است؟</b>\n"
    "سرورها دارای پهنای باند بالا هستند. البته گاهی برای تغییرات آی‌پی، ممکن است اختلال‌های کوتاه‌مدت (5 تا 15 دقیقه‌ای) رخ دهد، اما به طور کلی اتصال پایدار و مناسبی فراهم است.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    f"{p('info')}<b>۴. چه برنامه‌هایی پشتیبانی می‌شوند؟</b>\n"
    "برنامه‌هایی مانند Hiddify، V2Box، V2rayNG، Streisand و سایر اپ‌ها پشتیبانی می‌شوند. لینک دانلود اپلیکیشن‌ها از منوی اصلی در دسترس است.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    f"{p('info')}<b>۵. آیا بر روی تمام اپراتورهای ایران کار می‌کند؟</b>\n"
    "بله، تمام سرویس‌ها روی تمامی اپراتورهای کشور فعال هستند و هیچ محدودیت منطقه‌ای وجود ندارد.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    f"{p('info')}<b>۶. حجم واقعی است یا ضریب دارد؟</b>\n"
    "حجم خریداری‌شده به همان مقدار واقعی مصرف می‌شود و هیچ ضریب یا تبدیل وجود ندارد. همچنین می‌توانید هر زمان که مایل بودید مصرف دقیق خود را با لینک ساب بررسی نمایید.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    f"{p('chat')}اگر سوال دیگری دارید، با پشتیبانی در تماس باشید.\n"
    "خرید تنها از ربات @{bot_username} انجام می‌شود.\n\n"
    "@{support_username}"
)

# ─── Admin dashboard ─────────────────────────────────────────────────────────

ADMIN_DASHBOARD = (
    f"{p('admin')}<b>پنل مدیریت ان‌سی‌ وی‌پی‌ان</b>\n\n"
    f"{p('chart')}<b>آمار امروز:</b>\n"
    "• کاربران جدید: {today_users}\n"
    "• درآمد امروز: {today_revenue} تومان\n\n"
    f"{p('chart')}<b>آمار کلی:</b>\n"
    "• کل کاربران: {total_users}\n"
    "• سرویس‌های فعال: {active_configs}\n"
    "• کل درآمد: {total_revenue} تومان\n\n"
    f"{p('server')}<b>وضعیت سرور:</b>\n"
    "• CPU: {cpu}٪\n"
    "• RAM: {ram}٪\n"
    "• Xray: {xray_state}"
)

ADMIN_DISCOUNT_CREATED = (
    f"{p('confirm')}<b>کد تخفیف ایجاد شد!</b>\n\n"
    f"{p('ticket')}کد: <code>{{code}}</code>\n"
    f"{p('wallet')}تخفیف: {{value}}\n"
    f"{p('chart')}حداکثر استفاده: {{max_uses}}\n"
    f"{p('clock')}انقضا: {{expires}}"
)
ADMIN_DISCOUNT_LIST_HEADER = f"{p('ticket')}<b>کدهای تخفیف فعال</b>\n"
ADMIN_DISCOUNT_ROW = (
    "──────────────────\n"
    f"{p('ticket')}<code>{{code}}</code>\n"
    f"{p('wallet')}{{value}}\n"
    f"{p('chart')}{{used}}/{{max_uses}}\n"
    f"{p('clock')}انقضا: {{expires}}"
)
ADMIN_DISCOUNT_NOT_FOUND = f"{p('error')}کد تخفیف پیدا نشد."
ADMIN_DISCOUNT_DEACTIVATED = f"{p('trash')}کد <code>{{code}}</code> غیرفعال شد."
ADMIN_DISCOUNT_STATS = (
    f"{p('chart')}<b>آمار کد {{code}}</b>\n\n"
    f"{p('chart')}استفاده شده: {{used}}/{{max_uses}}\n"
    f"{p('clock')}ساخته شده: {{created}}\n"
    f"{p('clock')}انقضا: {{expires}}\n"
    "وضعیت: {state}"
)
ADMIN_DISCOUNT_USAGE_HELP = (
    "استفاده:\n"
    "<code>/addcode CODE PERCENT|AMOUNT USES EXPIRE_DAYS</code>\n\n"
    "مثال:\n"
    "<code>/addcode SUMMER10 10% 100 7</code>\n"
    "<code>/addcode FLAT5000 5000t 50 2</code>"
)

# ─── Notifications ───────────────────────────────────────────────────────────

NOTIF_EXPIRY_WARNING = (
    f"{p('warning')}<b>سرویس شما رو به اتمام است!</b>\n\n"
    f"{p('tag')}نام: {{name}}\n"
    f"{p('clock')}انقضا: {{expiry}} ({{days}} روز دیگر)\n"
    f"{p('chart')}حجم باقیمانده: {{remaining_gb}} گیگ\n\n"
    f"{p('gift')}<b>تمدید با {{discount_pct}}٪ تخفیف</b> — حجم افزایش + {{max_days}} روز پس از اولین اتصال."
)
NOTIF_TRAFFIC_WARNING = (
    f"{p('warning')}<b>حجم سرویس شما رو به اتمام است!</b>\n\n"
    f"{p('tag')}نام: {{name}}\n"
    f"{p('chart')}مصرف: {{used_gb}} از {{total_gb}} گیگ ({{pct}}٪)\n\n"
    f"{p('gift')}<b>تمدید با {{discount_pct}}٪ تخفیف</b> — حجم افزایش + {{max_days}} روز پس از اولین اتصال."
)
NOTIF_RENEW_BTN = "تمدید با {discount_pct}٪ تخفیف"
NOTIF_NEW_CONFIG_BTN = "خرید سرویس جدید"

# ─── Misc UI strings ─────────────────────────────────────────────────────────

WAIT_CREATING = f"{p('pending')}در حال ایجاد سرویس…"
WAIT_PROCESSING = f"{p('pending')}در حال پردازش…"
TX_DESC_PURCHASE = "خرید {plan_name} × {qty} ({name})"
TX_DESC_WALLET = "شارژ کیف پول"
TX_DESC_REFERRAL_RECEIVED = "هدیه معرفی دوست"
TX_DESC_REFERRAL_FRIEND = "هدیه ورود با لینک معرف"
