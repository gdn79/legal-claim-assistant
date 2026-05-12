from __future__ import annotations

import re
from typing import Any

from .claim_scenario import SCENARIO_LABELS, scenario_requirements


REQUIRED_PARTY_FIELDS = ("name", "inn", "ogrn", "address")
REQUIRED_SCENARIO_CODES = set(SCENARIO_LABELS)

# Known articles of Russian codes for legal reference validation
KNOWN_ARTICLES_GK = frozenset({
    "1", "2", "8", "9", "10", "11", "12", "15", "16", "53", "54", "56",
    "57", "61", "62", "63", "64", "65", "66", "67", "68", "69", "70",
    "87", "88", "89", "90", "91", "94", "96", "97", "98", "99", "100",
    "101", "102", "103", "104", "105", "106", "107", "108", "109", "110",
    "111", "113", "114", "115", "116", "117", "118", "119", "120", "121",
    "122", "123", "124", "125", "128", "129", "130", "131", "132", "133",
    "134", "135", "136", "137", "138", "139", "140", "141", "142", "144",
    "145", "146", "147", "148", "149", "150", "151", "152", "153", "154",
    "155", "156", "157", "158", "159", "160", "161", "162", "163", "164",
    "165", "166", "167", "168", "169", "170", "171", "172", "173", "174",
    "175", "176", "177", "178", "179", "180", "181", "182", "183", "184",
    "185", "186", "187", "188", "189", "190", "191", "192", "193", "194",
    "195", "196", "197", "198", "199", "200", "201", "202", "203", "204",
    "205", "206", "207", "208", "209", "210", "217", "218", "219", "220",
    "221", "222", "223", "224", "225", "226", "227", "228", "229", "230",
    "231", "232", "233", "234", "235", "236", "237", "238", "239", "240",
    "241", "242", "243", "244", "245", "246", "247", "248", "249", "250",
    "251", "252", "253", "254", "255", "256", "257", "258", "259", "260",
    "261", "262", "263", "264", "265", "266", "267", "268", "269", "270",
    "271", "272", "273", "274", "275", "276", "277", "278", "279", "280",
    "281", "282", "283", "284", "285", "286", "287", "288", "289", "290",
    "291", "292", "293", "294", "295", "296", "297", "298", "299", "300",
    "301", "302", "303", "304", "305", "306", "307", "308", "309", "310",
    "311", "312", "313", "314", "315", "316", "317", "318", "319", "320",
    "321", "322", "323", "324", "325", "326", "327", "328", "329", "330",
    "331", "332", "333", "334", "335", "336", "337", "338", "339", "340",
    "341", "342", "343", "344", "345", "346", "347", "348", "349", "350",
    "351", "352", "353", "354", "355", "356", "357", "358", "359", "360",
    "361", "362", "363", "364", "365", "366", "367", "368", "369", "370",
    "371", "372", "373", "374", "375", "376", "377", "378", "379", "380",
    "381", "382", "383", "384", "385", "386", "387", "388", "389", "390",
    "391", "392", "393", "394", "395", "396", "397", "398", "399", "400",
    "401", "402", "403", "404", "405", "406", "407", "408", "409", "410",
    "411", "412", "413", "414", "415", "416", "417", "418", "419", "420",
    "421", "422", "423", "424", "425", "426", "427", "428", "429", "430",
    "431", "432", "433", "434", "435", "436", "437", "438", "439", "440",
    "441", "442", "443", "444", "445", "446", "447", "448", "449", "450",
    "451", "452", "453", "454", "455", "456", "457", "458", "459", "460",
    "461", "462", "463", "464", "465", "466", "467", "468", "469", "470",
    "471", "472", "473", "474", "475", "476", "477", "478", "479", "480",
    "481", "482", "483", "484", "485", "486", "487", "488", "489", "490",
    "491", "492", "493", "494", "495", "496", "497", "498", "499", "500",
    "501", "502", "503", "504", "505", "506", "507", "508", "509", "510",
    "511", "512", "513", "514", "515", "516", "517", "518", "519", "520",
    "521", "522", "523", "524", "525", "526", "527", "528", "529", "530",
    "531", "532", "533", "534", "535", "536", "537", "538", "539", "540",
    "541", "542", "543", "544", "545", "546", "547", "548", "549", "550",
    "551", "552", "553", "554", "555", "556", "557", "558", "559", "560",
    "561", "562", "563", "564", "565", "566", "567", "568", "569", "570",
    "571", "572", "573", "574", "575", "576", "577", "578", "579", "580",
    "581", "582", "583", "584", "585", "586", "587", "588", "589", "590",
    "591", "592", "593", "594", "595", "596", "597", "598", "599", "600",
    "601", "602", "603", "604", "605", "606", "607", "608", "609", "610",
    "611", "612", "613", "614", "615", "616", "617", "618", "619", "620",
    "621", "622", "623", "624", "625", "626", "627", "628", "629", "630",
    "631", "632", "633", "634", "635", "636", "637", "638", "639", "640",
    "641", "642", "643", "644", "645", "646", "647", "648", "649", "650",
    "651", "652", "653", "654", "655", "656", "657", "658", "659", "660",
    "661", "662", "663", "664", "665", "666", "667", "668", "669", "670",
    "671", "672", "673", "674", "675", "676", "677", "678", "679", "680",
    "681", "682", "683", "684", "685", "686", "687", "688", "689", "690",
    "691", "692", "693", "694", "695", "696", "697", "698", "699", "700",
    "701", "702", "703", "704", "705", "706", "707", "708", "709", "710",
    "711", "712", "713", "714", "715", "716", "717", "718", "719", "720",
    "721", "722", "723", "724", "725", "726", "727", "728", "729", "730",
    "731", "732", "733", "734", "735", "736", "737", "738", "739", "740",
    "741", "742", "743", "744", "745", "746", "747", "748", "749", "750",
    "751", "752", "753", "754", "755", "756", "757", "758", "759", "760",
    "761", "762", "763", "764", "765", "766", "767", "768", "769", "770",
    "771", "772", "773", "774", "775", "776", "777", "778", "779", "780",
    "781", "782", "783", "784", "785", "786", "787", "788", "789", "790",
    "791", "792", "793", "794", "795", "796", "797", "798", "799", "800",
    "801", "802", "803", "804", "805", "806", "807", "808", "809", "810",
    "811", "812", "813", "814", "815", "816", "817", "818", "819", "820",
    "821", "822", "823", "824", "825", "826", "827", "828", "829", "830",
    "831", "832", "833", "834", "835", "836", "837", "838", "839", "840",
    "841", "842", "843", "844", "845", "846", "847", "848", "849", "850",
    "851", "852", "853", "854", "855", "856", "857", "858", "859", "860",
    "861", "862", "863", "864", "865", "866", "867", "868", "869", "870",
    "871", "872", "873", "874", "875", "876", "877", "878", "879", "880",
    "881", "882", "883", "884", "885", "886", "887", "888", "889", "890",
    "891", "892", "893", "894", "895", "896", "897", "898", "899", "900",
    "901", "902", "903", "904", "905", "906", "907", "908", "909", "910",
    "911", "912", "913", "914", "915", "916", "917", "918", "919", "920",
    "921", "922", "923", "924", "925", "926", "927", "928", "929", "930",
    "931", "932", "933", "934", "935", "936", "937", "938", "939", "940",
    "941", "942", "943", "944", "945", "946", "947", "948", "949", "950",
    "951", "952", "953", "954", "955", "956", "957", "958", "959", "960",
    "961", "962", "963", "964", "965", "966", "967", "968", "969", "970",
    "971", "972", "973", "974", "975", "976", "977", "978", "979", "980",
    "981", "982", "983", "984", "985", "986", "987", "988", "989", "990",
    "991", "992", "993", "994", "995", "996", "997", "998", "999",
    "1000", "1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008",
    "1009", "1010", "1011", "1012", "1013", "1014", "1015", "1016", "1017",
    "1018", "1019", "1020", "1021", "1022", "1023", "1024", "1025", "1026",
    "1027", "1028", "1029", "1030", "1031", "1032", "1033", "1034", "1035",
    "1036", "1037", "1038", "1039", "1040", "1041", "1042", "1043", "1044",
    "1045", "1046", "1047", "1048", "1049", "1050", "1051", "1052", "1053",
    "1054", "1055", "1056", "1057", "1058", "1059", "1060", "1061", "1062",
    "1063", "1064", "1065", "1066", "1067", "1068", "1069", "1070", "1071",
    "1072", "1073", "1074", "1075", "1076", "1077", "1078", "1079", "1080",
    "1081", "1082", "1083", "1084", "1085", "1086", "1087", "1088", "1089",
    "1090", "1091", "1092", "1093", "1094", "1095", "1096", "1097", "1098",
    "1099", "1100", "1101", "1102", "1103", "1104", "1105", "1106", "1107",
    "1108", "1109", "1110", "1111", "1112", "1113", "1114", "1115", "1116",
    "1117", "1118", "1119", "1120", "1121", "1122", "1123", "1124", "1125",
    "1126", "1127", "1128", "1129", "1130", "1131", "1132", "1133", "1134",
    "1135", "1136", "1137", "1138", "1139", "1140", "1141", "1142", "1143",
    "1144", "1145", "1146", "1147", "1148", "1149", "1150", "1151", "1152",
    "1153", "1154", "1155",
})
KNOWN_ARTICLES_APK = frozenset({
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13",
    "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25",
    "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36", "37",
    "38", "39", "40", "41", "42", "43", "44", "45", "46", "47", "48", "49",
    "50", "51", "52", "53", "54", "55", "56", "57", "58", "59", "60", "61",
    "62", "63", "64", "65", "66", "67", "68", "69", "70", "71", "72", "73",
    "74", "75", "76", "77", "78", "79", "80", "81", "82", "83", "84", "85",
    "86", "87", "88", "89", "90", "91", "92", "93", "94", "95", "96", "97",
    "98", "99", "100", "101", "102", "103", "104", "105", "106", "107",
    "108", "109", "110", "111", "112", "113", "114", "115", "116", "117",
    "118", "119", "120", "121", "122", "123", "124", "125", "126", "127",
    "128", "129", "130", "131", "132", "133", "134", "135", "136", "137",
    "138", "139", "140", "141", "142", "143", "144", "145", "146", "147",
    "148", "149", "150", "151", "152", "153", "154", "155", "156", "157",
    "158", "159", "160", "161", "162", "163", "164", "165", "166", "167",
    "168", "169", "170", "171", "172", "173", "174", "175", "176", "177",
    "178", "179", "180", "181", "182", "183", "184", "185", "186", "187",
    "188", "189", "190", "191", "192", "193", "194", "195", "196", "197",
    "198", "199", "200", "201", "202", "203", "204", "205", "206", "207",
    "208", "209", "210", "211", "212", "213", "214", "215", "216", "217",
    "218", "219", "220", "221", "222", "223", "224", "225", "226", "227",
    "228", "229", "230", "231", "232", "233", "234", "235", "236", "237",
    "238", "239", "240", "241", "242", "243", "244", "245", "246", "247",
    "248", "249", "250", "251", "252", "253", "254", "255", "256", "257",
    "258", "259", "260", "261", "262", "263", "264", "265", "266", "267",
    "268", "269", "270", "271", "272", "273", "274", "275", "276", "277",
    "278", "279", "280", "281", "282", "283", "284", "285", "286", "287",
    "288", "289", "290", "291", "292", "293", "294", "295", "296", "297",
    "298", "299", "300", "301", "302", "303", "304", "305", "306", "307",
    "308", "309", "310", "311", "312", "313", "314", "315", "316", "317",
    "318", "319", "320", "321", "322", "323", "324", "325", "326", "327",
    "328", "329", "330", "331", "332", "333", "334", "335", "336", "337",
    "338", "339", "340", "341", "342",
})
KNOWN_ARTICLES_NK = frozenset({
    "3", "8", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32",
    "33", "34", "35", "36", "37", "38", "39", "40", "41", "42", "43", "44",
    "45", "46", "47", "48", "49", "50", "51", "52", "53", "54", "55", "56",
    "57", "58", "59", "60", "61", "62", "63", "64", "65", "66", "67", "68",
    "69", "70", "71", "72", "73", "74", "75", "76", "77", "78", "79", "80",
    "81", "82", "83", "84", "85", "86", "87", "88", "89", "90", "91", "92",
    "93", "94", "95", "96", "97", "98", "99", "100", "101", "102", "103",
    "104", "105", "106", "107", "108", "109", "110", "111", "112", "113",
    "114", "115", "116", "117", "118", "119", "120", "121", "122", "123",
    "124", "125", "126", "127", "128", "129", "130", "131", "132", "133",
    "134", "135", "136", "137", "138", "139", "140", "141", "142", "143",
    "144", "145", "146", "147", "148", "149", "150", "151", "152", "153",
    "154", "155", "156", "157", "158", "159", "160", "161", "162", "163",
    "164", "165", "166", "167", "168", "169", "170", "171", "172", "173",
    "174", "175", "176", "177", "178", "179", "180", "181", "182", "183",
    "184", "185", "186", "187", "188", "189", "190", "191", "192", "193",
    "194", "195", "196", "197", "198", "199", "200", "201", "202", "203",
    "204", "205", "206", "207", "208", "209", "210", "211", "212", "213",
    "214", "215", "216", "217", "218", "219", "220", "221", "222", "223",
    "224", "225", "226", "227", "228", "229", "230", "231", "232", "233",
    "234", "235", "236", "237", "238", "239", "240", "241", "242", "243",
    "244", "245", "246", "247", "248", "249", "250", "251", "252", "253",
    "254", "255", "256", "257", "258", "259", "260", "261", "262", "263",
    "264", "265", "266", "267", "268", "269", "270", "271", "272", "273",
    "274", "275", "276", "277", "278", "279", "280", "281", "282", "283",
    "284", "285", "286", "287", "288", "289", "290", "291", "292", "293",
    "294", "295", "296", "297", "298", "299", "300", "301", "302", "303",
    "304", "305", "306", "307", "308", "309", "310", "311", "312", "313",
    "314", "315", "316", "317", "318", "319", "320", "321", "322", "323",
    "324", "325", "326", "327", "328", "329", "330", "331", "332", "333",
    "333.1", "333.21", "333.22", "333.23", "333.24", "333.25", "333.26",
    "333.27", "333.28", "333.29", "333.30", "333.31", "333.32", "333.33",
    "333.34", "333.35", "333.36", "333.37", "333.38", "333.39", "333.40",
    "333.41", "333.42", "333.43", "333.44", "333.45", "334", "335", "336", "337", "338", "339", "340", "341", "342",
    "343", "344", "345", "346", "347", "348", "349", "350", "351", "352",
    "353", "354", "355", "356", "357", "358", "359", "360", "361", "362",
    "363", "364", "365", "366", "367", "368", "369", "370", "371", "372",
    "373", "374", "375", "376", "377", "378", "379", "380", "381", "382",
    "383", "384", "385", "386", "387", "388", "389", "390", "391", "392",
    "393", "394", "395", "396", "397", "398", "399", "400", "401", "402",
    "403", "404", "405", "406", "407", "408", "409", "410", "411", "412",
    "413", "414", "415", "416", "417", "418", "419", "420", "421", "422",
    "423", "424", "425", "426", "427", "428", "429", "430", "431", "432",
    "433", "434", "435", "436", "437", "438", "439", "440", "441", "442",
    "443", "444", "445", "446", "447", "448", "449", "450", "451", "452",
    "453", "454", "455", "456", "457", "458", "459", "460",
})


def build_case_profile(analysis: dict[str, Any]) -> dict[str, Any]:
    claimant = analysis.get("claimant") or {}
    defendant = analysis.get("defendant") or {}
    amounts = analysis.get("amounts") or {}
    calculation = analysis.get("claim_calculation") or {}
    contract = _first_contract(analysis)
    scenario = analysis.get("claim_scenario") or {}
    pretrial = analysis.get("pretrial") or {}
    sufficiency = analysis.get("sufficiency") or {}

    return {
        "claimant": _party_profile(claimant),
        "defendant": _party_profile(defendant),
        "claim_type": analysis.get("claim_type") or "",
        "scenario": {
            "code": scenario.get("code") or "generic_debt",
            "label": scenario.get("label") or "Взыскание задолженности",
            "reason": scenario.get("reason") or "",
        },
        "contract": {
            "number": contract.get("number") or "",
            "date": contract.get("date") or "",
            "subject": contract.get("subject") or "",
            "amount": contract.get("amount") or "",
        },
        "amounts": {
            "principal_debt": _money(amounts.get("principal_debt")),
            "penalty": _money(amounts.get("penalty")),
            "interest_395": _money(amounts.get("interest_395")),
            "other": _money(amounts.get("other")),
            "total": _money(amounts.get("total")),
        },
        "pretrial": {
            "claim_sent": bool(pretrial.get("claim_sent")),
            "claim_date": pretrial.get("claim_date") or "",
            "delivery_evidence": pretrial.get("delivery_evidence") or "",
            "notes": pretrial.get("notes") or "",
        },
        "documents": {
            "contracts": len(analysis.get("contracts") or []),
            "acts": len(analysis.get("acts") or []),
            "payments": len(analysis.get("payments") or []),
            "has_reconciliation": _has_text(analysis, ("сверк", "сальдо", "задолженность в пользу")),
            "has_pretrial": bool(pretrial.get("claim_sent")),
            "has_payment_docs": len(analysis.get("payments") or []) > 0 or _has_text(analysis, ("платеж", "платёж", "п/п")),
            "has_calculation": _has_calculation(analysis),
            "missing": list(sufficiency.get("missing") or []),
            "enough": bool(sufficiency.get("enough")),
        },
        "calculation": {
            "state_duty_rub": calculation.get("state_duty_rub") or 0,
            "state_duty_calculation": calculation.get("state_duty_calculation") or "",
            "warnings": list(calculation.get("warnings") or []),
        },
        "risks": list(analysis.get("risks") or []),
        "questions_for_user": list(analysis.get("questions_for_user") or []),
    }


def build_readiness_report(
    analysis: dict[str, Any],
    *,
    stage: str,
    generated_claim_text: str | None = None,
    validation_warnings: list[str] | None = None,
) -> dict[str, Any]:
    profile = build_case_profile(analysis)
    checklist = [
        _documents_check(profile),
        _scenario_documents_check(profile),
        _parties_check(profile),
        _scenario_check(profile),
        _amounts_check(profile),
        _calculation_check(profile),
        _pretrial_check(profile),
        _company_details_check(profile),
        _attachments_check(profile),
    ]

    if stage == "claim":
        checklist.append(_claim_text_check(generated_claim_text or "", validation_warnings or []))
    else:
        checklist.append(
            _item(
                "docx",
                "Текст иска",
                "pending",
                0,
                10,
                "Появится после подтверждения карточки дела и генерации DOCX.",
            )
        )

    percent = round(sum(item["score"] for item in checklist) / sum(item["max_score"] for item in checklist) * 100)
    blockers = [item for item in checklist if item["status"] == "block"]
    warnings = [item for item in checklist if item["status"] == "warn"]
    return {
        "stage": stage,
        "readiness_percent": min(100, max(0, percent)),
        "status": "blocked" if blockers else ("claim_ready" if stage == "claim" else "needs_review"),
        "can_download": stage == "claim" and not blockers,
        "profile": profile,
        "checklist": checklist,
        "blockers": blockers,
        "warnings": warnings,
    }


def validate_generated_claim(claim_text: str, analysis: dict[str, Any], scenario_warnings: list[str]) -> list[str]:
    critical: list[str] = []
    scenario = ((analysis.get("claim_scenario") or {}).get("code") or "").strip()

    if scenario in {"reconciliation_balance", "customer_refund"}:
        if re.search(r"истец[^.\n]{0,140}(?:выполнил|оказал)\s+(?:работ|услуг)", claim_text, re.IGNORECASE):
            critical.append("Иск описывает истца как исполнителя работ при сценарии акта сверки/возврата.")
        if re.search(r"ответчик[^.\n]{0,140}не\s+(?:исполнил\s+)?(?:оплатил|осуществил\s+оплату)", claim_text, re.IGNORECASE):
            critical.append("Иск использует фабулу неоплаты работ ответчиком, хотя выбран сценарий акта сверки/возврата.")

    if re.search(r"(если хотите|если необходимо|хотите, чтобы я|я могу подготовить|готов подготовить)", claim_text, re.IGNORECASE):
        critical.append("В тексте остался разговорный хвост ИИ.")
    if re.search(r"```|\*\*|^---$", claim_text, re.MULTILINE):
        critical.append("В тексте осталась markdown-разметка.")

    for warning in scenario_warnings:
        if warning not in critical:
            critical.append(warning)

    critical.extend(_check_legal_references(claim_text))
    critical.extend(_check_mandatory_requisites(claim_text, analysis))
    return critical


def _check_legal_references(claim_text: str) -> list[str]:
    warnings: list[str] = []
    for code_label, articles, name in [
        ("ГК РФ", KNOWN_ARTICLES_GK, "ГК РФ"),
        ("АПК РФ", KNOWN_ARTICLES_APK, "АПК РФ"),
    ]:
        for match in re.finditer(rf"ст\.\s*([\d.]+)\s+{re.escape(code_label)}", claim_text, re.IGNORECASE):
            article = match.group(1)
            if article not in articles:
                warnings.append(f"Ссылка на несуществующую статью {article} {name}.")
    for match in re.finditer(rf"ст\.\s*([\d.]+)\s+НК РФ", claim_text, re.IGNORECASE):
        article = match.group(1)
        if article not in KNOWN_ARTICLES_NK:
            warnings.append(f"Ссылка на несуществующую статью {article} НК РФ.")
    return warnings


REQUISITE_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("court_name", re.compile(r"арбитражный суд", re.IGNORECASE), "Не указано наименование арбитражного суда."),
    ("claim_price", re.compile(r"цен[аы]\s+иска", re.IGNORECASE), "Не указана цена иска."),
    ("claimant_info", re.compile(r"истец\s*:", re.IGNORECASE), "Отсутствует блок с данными истца."),
    ("defendant_info", re.compile(r"ответчик\s*:", re.IGNORECASE), "Отсутствует блок с данными ответчика."),
    ("prositive_part", re.compile(r"прош[уу]", re.IGNORECASE), "Отсутствует просительная часть (Прошу)."),
    ("gosposhlina", re.compile(r"госпошлин", re.IGNORECASE), "Не упомянута госпошлина."),
]


def _check_mandatory_requisites(claim_text: str, analysis: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for _key, pattern, message in REQUISITE_PATTERNS:
        if not pattern.search(claim_text):
            warnings.append(message)
    return warnings


def _documents_check(profile: dict[str, Any]) -> dict[str, Any]:
    docs = profile["documents"]
    has_contract = docs["contracts"] > 0
    has_evidence = docs["acts"] > 0 or docs["payments"] > 0
    if has_contract and has_evidence:
        return _item("documents", "Документы", "ok", 15, 15, "Есть договор и документы, подтверждающие исполнение/оплату.")
    if has_contract or has_evidence:
        return _item("documents", "Документы", "warn", 8, 15, "Есть часть доказательств, но комплект нужно проверить.")
    return _item("documents", "Документы", "block", 0, 15, "Не найден договор или ключевые доказательства.")


def _scenario_documents_check(profile: dict[str, Any]) -> dict[str, Any]:
    scenario_code = profile["scenario"]["code"]
    requirements = scenario_requirements(scenario_code)
    docs = profile["documents"]
    missing_required = []

    for requirement in requirements["required"]:
        if not _requirement_met(requirement, docs):
            missing_required.append(requirement)

    if not missing_required:
        return _item(
            "scenario_documents",
            "Документы по модели",
            "ok",
            15,
            15,
            "Обязательный комплект для модели иска выглядит закрытым.",
        )
    if len(missing_required) <= 2:
        return _item(
            "scenario_documents",
            "Документы по модели",
            "warn",
            8,
            15,
            "Нужно проверить/добавить: " + "; ".join(missing_required),
        )
    return _item(
        "scenario_documents",
        "Документы по модели",
        "block",
        0,
        15,
        "Не хватает обязательных документов: " + "; ".join(missing_required),
    )


def _parties_check(profile: dict[str, Any]) -> dict[str, Any]:
    missing = []
    for side in ("claimant", "defendant"):
        party = profile[side]
        side_label = "истца" if side == "claimant" else "ответчика"
        for field in REQUIRED_PARTY_FIELDS:
            if not party.get(field):
                missing.append(f"{side_label}: {field}")
    if not missing:
        return _item("parties", "Стороны", "ok", 15, 15, "Истец и ответчик заполнены с ИНН, ОГРН и адресами.")
    if len(missing) <= 3:
        return _item("parties", "Стороны", "warn", 9, 15, "Нужно дополнить: " + ", ".join(missing))
    return _item("parties", "Стороны", "block", 0, 15, "Недостаточно данных по сторонам: " + ", ".join(missing))


def _scenario_check(profile: dict[str, Any]) -> dict[str, Any]:
    scenario = profile["scenario"]
    if scenario["code"] in REQUIRED_SCENARIO_CODES and scenario["reason"]:
        return _item("scenario", "Модель иска", "ok", 15, 15, scenario["label"])
    if scenario["code"] in REQUIRED_SCENARIO_CODES:
        return _item("scenario", "Модель иска", "warn", 10, 15, "Модель выбрана, но причину лучше проверить вручную.")
    return _item("scenario", "Модель иска", "block", 0, 15, "Не выбран сценарий требований.")


def _amounts_check(profile: dict[str, Any]) -> dict[str, Any]:
    amounts = profile["amounts"]
    if amounts["total"] > 0:
        return _item("amounts", "Цена иска", "ok", 15, 15, f"Цена иска: {amounts['total']:,.2f} руб.".replace(",", " "))
    if amounts["principal_debt"] > 0:
        return _item("amounts", "Цена иска", "warn", 11, 15, "Есть основной долг, но итоговая цена иска не заполнена.")
    return _item("amounts", "Цена иска", "block", 0, 15, "Не определена сумма требований.")


def _calculation_check(profile: dict[str, Any]) -> dict[str, Any]:
    calculation = profile["calculation"]
    warnings = calculation["warnings"]
    if not warnings and calculation["state_duty_rub"]:
        return _item("calculation", "Расчет требований", "ok", 10, 10, "Суммы нормализованы, госпошлина рассчитана.")
    if warnings:
        return _item("calculation", "Расчет требований", "warn", 5, 10, "; ".join(warnings))
    return _item("calculation", "Расчет требований", "warn", 4, 10, "Расчет требует ручной проверки.")


def _pretrial_check(profile: dict[str, Any]) -> dict[str, Any]:
    pretrial = profile["pretrial"]
    if pretrial["claim_sent"] and pretrial["delivery_evidence"]:
        return _item("pretrial", "Претензионный порядок", "ok", 10, 10, "Претензия и доказательства направления указаны.")
    if pretrial["claim_sent"]:
        return _item("pretrial", "Претензионный порядок", "warn", 6, 10, "Претензия указана, но доказательство направления нужно проверить.")
    return _item("pretrial", "Претензионный порядок", "warn", 3, 10, "Претензия не подтверждена. Для многих споров это риск возврата иска.")


def _company_details_check(profile: dict[str, Any]) -> dict[str, Any]:
    missing = []
    for side in ("claimant", "defendant"):
        party = profile[side]
        if not party.get("kpp"):
            missing.append(("истец" if side == "claimant" else "ответчик") + ": КПП")
        if not party.get("representative"):
            missing.append(("истец" if side == "claimant" else "ответчик") + ": руководитель/представитель")
    if not missing:
        return _item("company_details", "Реквизиты компаний", "ok", 10, 10, "Реквизиты заполнены.")
    return _item("company_details", "Реквизиты компаний", "warn", 5, 10, "Нужно проверить: " + ", ".join(missing))


def _attachments_check(profile: dict[str, Any]) -> dict[str, Any]:
    missing = profile["documents"]["missing"]
    if not missing:
        return _item("attachments", "Приложения", "ok", 10, 10, "ИИ не отметил недостающие документы.")
    if len(missing) <= 3:
        return _item("attachments", "Приложения", "warn", 6, 10, "Проверьте недостающие документы: " + "; ".join(missing))
    return _item("attachments", "Приложения", "warn", 4, 10, "Много недостающих документов: " + "; ".join(missing[:5]))


def _claim_text_check(claim_text: str, validation_warnings: list[str]) -> dict[str, Any]:
    if validation_warnings:
        return _item("docx", "Текст иска", "block", 0, 10, "Критические замечания: " + "; ".join(validation_warnings))
    if len(claim_text.strip()) < 1200:
        return _item("docx", "Текст иска", "warn", 5, 10, "Текст выглядит слишком коротким для полноценного иска.")
    return _item("docx", "Текст иска", "ok", 10, 10, "Текст прошел автоматическую проверку.")


def _party_profile(party: dict[str, Any]) -> dict[str, str]:
    return {
        "name": str(party.get("name") or ""),
        "inn": str(party.get("inn") or ""),
        "ogrn": str(party.get("ogrn") or ""),
        "kpp": str(party.get("kpp") or ""),
        "address": str(party.get("address") or ""),
        "representative": str(party.get("representative") or ""),
    }


def _first_contract(analysis: dict[str, Any]) -> dict[str, Any]:
    contracts = analysis.get("contracts") or []
    if contracts and isinstance(contracts[0], dict):
        return contracts[0]
    return {}


def _money(value: Any) -> float:
    try:
        normalized = str(value or 0).replace(" ", "").replace("\xa0", "").replace(",", ".")
        return float(normalized)
    except (TypeError, ValueError):
        return 0.0


def _item(key: str, title: str, status: str, score: int, max_score: int, note: str) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "status": status,
        "score": score,
        "max_score": max_score,
        "note": note,
    }


def _requirement_met(requirement: str, docs: dict[str, Any]) -> bool:
    normalized = requirement.lower()
    if "договор" in normalized or "счет" in normalized or "счёт" in normalized or "основание" in normalized:
        return docs["contracts"] > 0
    if "акт сверки" in normalized or "сальдо" in normalized:
        return bool(docs["has_reconciliation"])
    if "акт/" in normalized or "упд" in normalized or "наклад" in normalized or "закрывающ" in normalized:
        return docs["acts"] > 0
    if "платеж" in normalized or "платёж" in normalized or "аванс" in normalized or "предоплат" in normalized:
        return bool(docs["has_payment_docs"])
    if "расчет" in normalized or "расчёт" in normalized or "период" in normalized or "дата начала" in normalized:
        return bool(docs["has_calculation"])
    if "отсутств" in normalized or "расторжен" in normalized or "правового основания" in normalized:
        return bool(docs["has_reconciliation"] or docs["missing"])
    return True


def _has_text(analysis: dict[str, Any], needles: tuple[str, ...]) -> bool:
    haystack = str(analysis).lower()
    return any(needle in haystack for needle in needles)


def _has_calculation(analysis: dict[str, Any]) -> bool:
    amounts = analysis.get("amounts") or {}
    if _money(amounts.get("total")) > 0 or _money(amounts.get("principal_debt")) > 0:
        return True
    return _has_text(analysis, ("расчет", "расчёт", "период просрочки", "ставка"))
