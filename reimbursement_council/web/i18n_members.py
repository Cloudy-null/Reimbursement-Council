"""Text for adding a member by hand, in English and Arabic. Merged into i18n.TEXT.

The error keys are the codes core/new_member.py returns.
"""

MEMBER_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "member_add_link": "Add a person",
        "member_title": "Add a member",
        "member_intro": "Add a person to test a claim with. Their policy is active from one "
        "year before today to one year after.",
        "member_name": "Name (English)",
        "member_name_ar": "Name in Arabic (optional)",
        "member_tier": "Policy tier",
        "member_dependants": "Family on the policy (one name per line, up to 5)",
        "member_used_title": "Benefit used so far (SAR)",
        "member_save": "Add member",
        "member_errors": "Please fix the fields marked below.",
        "member_name_missing": "Write a name.",
        "member_name_length": "A name must be 2 to 80 letters.",
        "member_name_digits": "A name cannot have numbers.",
        "member_tier_unknown": "Pick a tier from the list.",
        "member_too_many": "Up to 5 family members.",
        "member_amount_bad": "Write the amount like 600 or 600.00.",
        "member_benefit_unknown": "This benefit is not in the policy.",
    },
    "ar": {
        "member_add_link": "أضف شخصا",
        "member_title": "أضف عضوا",
        "member_intro": "أضف شخصا لتجربة مطالبة. وثيقته سارية من سنة قبل اليوم إلى سنة بعده.",
        "member_name": "الاسم بالإنجليزية",
        "member_name_ar": "الاسم بالعربية (اختياري)",
        "member_tier": "فئة الوثيقة",
        "member_dependants": "أفراد الأسرة في الوثيقة (اسم في كل سطر، حتى 5)",
        "member_used_title": "ما استخدم من المنافع حتى الآن (ريال)",
        "member_save": "أضف العضو",
        "member_errors": "صحح الحقول المحددة أدناه.",
        "member_name_missing": "اكتب الاسم.",
        "member_name_length": "يجب أن يكون الاسم من 2 إلى 80 حرفا.",
        "member_name_digits": "لا يمكن أن يحتوي الاسم على أرقام.",
        "member_tier_unknown": "اختر فئة من القائمة.",
        "member_too_many": "حتى 5 أفراد فقط.",
        "member_amount_bad": "اكتب المبلغ مثل 600 أو 600.00.",
        "member_benefit_unknown": "هذه المنفعة ليست في الوثيقة.",
    },
}
