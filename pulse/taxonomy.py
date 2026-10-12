"""Issue taxonomy for MoveInSync reviews.

Built by reading ~600 recent 1-2 star reviews by hand, then encoding the recurring
complaints as regexes. Each review can carry several themes.

`owner` says who can fix it:
  app      -> mobile engineering
  product  -> product / UX decisions
  service  -> operations, vendors, transport desk (the app is just where it surfaces)
"""

import re

THEMES = [
    {
        "id": "integrity_block",
        "label": "\"Not installed from Play Store\" lockout",
        "owner": "app",
        "patterns": [
            r"showing not installed", r"updating the app every", r"not installed from",
            r"(not|wasn'?t|never) (been )?(installed|downloaded) (from|thr?o?u?g?h?|via) (the )?(google )?play ?store",
            r"(installed|downloaded) from (other|another|third)",
            r"not from (the )?play ?store",
            r"(uninstall|re-?install)\w* (it )?(again|every|after|frequent|very|daily|each)",
            r"only (solution|way|option) is (to )?(uninstall|re-?install)", r"installation",
            r"(have|need|had) to (uninstall|re-?install|download it again)",
            r"keeps? (on )?uninstalling",
        ],
    },
    {
        "id": "crash_wont_open",
        "label": "Crashes / won't open / blank screen",
        "owner": "app",
        "patterns": [
            r"not working", r"(doesn'?t|does not|don'?t) work", r"\bbugs?\b", r"buggy", r"glitch", r"something went wrong", r"\bdown\b", r"error",
            r"crash", r"(not|n'?t|never) (even )?open", r"not opening", r"won'?t (even )?(open|launch|start)",
            r"blank (white )?screen", r"stopped working", r"(close|closes|closing) (automatically|itself|on its own)",
            r"not (working|launching) (on|in|with) (my )?(android|pixel|samsung|oneplus|vivo|oppo|redmi|realme|iphone)",
            r"android (1[4-9]|version)", r"app error", r"force ?clos",
        ],
    },
    {
        "id": "login_otp",
        "label": "Login / OTP not received",
        "owner": "app",
        "patterns": [
            r"\botp\b", r"\bregister", r"one time password",
            r"otp\w* (is |are )?(not|never|isn'?t|doesn'?t|don'?t|didn'?t)", r"(not|never|no|didn'?t) (get|getting|receiv\w*|com\w*|send\w*|sent)\w* (any |the |an )?otp",
            r"no otp", r"(unable|not able|can'?t|cannot|couldn'?t) (to )?(log ?in|sign ?in|login|verify|register)",
            r"login (issue|problem|error|fail)", r"verification (fail|code|issue)", r"web login error",
        ],
    },
    {
        "id": "session_logout",
        "label": "Forced logouts / session expired",
        "owner": "app",
        "patterns": [
            r"log(s|ged|ging)? (me )?out", r"session expired", r"unauthori[sz]ed",
            r"(log ?in|login) (every|each) ?time", r"keep (us |me )?logged in", r"re-?login",
            r"(every|each) time (i |we )?(have|need) to log ?in", r"logouting", r"fingerprint",
        ],
    },
    {
        "id": "tracking_eta",
        "label": "Live tracking / ETA inaccurate",
        "owner": "app",
        "patterns": [
            r"location", r"navigation", r"\bmaps?\b", r"cab number",
            r"track(ing|er)?", r"\beta\b", r"gps", r"live location", r"(cab|vehicle|driver|bus|shuttle) location",
            r"location (is |was )?(not )?(updat|wrong|incorrect|stuck|old)", r"map (gets |is )?stuck",
            r"real ?-?time", r"arrival time",
        ],
    },
    {
        "id": "forced_prompts",
        "label": "Forced ratings, pop-ups, notification spam, permissions",
        "owner": "product",
        "patterns": [
            r"notif\w* .{0,30}(every ?time|again and again|repeated)", r"remind\w* me", r"reviews? after every ride",
            r"(force|forcing|compulsor|mandatory|compel)\w*", r"(no|without) (option to |any )?skip", r"skip (option|button|rating|feedback)",
            r"rat(e|ing) (after )?every", r"(keeps?|always) (on )?asking for (a )?rating", r"keep on sending notification", r"pop ?-?ups?", r"banner", r"too many notification", r"notifications? (all day|every|spam|without)",
            r"(so )?(many|lot of|unnecessary|excessive|annoying) notification", r"permission", r"\bads?\b", r"advertis",
            r"disclaimer", r"policy acceptance", r"only (given )?(options? )?(like )?4 or 5",
        ],
    },
    {
        "id": "ux_redesign",
        "label": "New UI / update made it worse",
        "owner": "product",
        "patterns": [
            r"(new|recent|latest|last) (update|version|ui|design|app|enhancement|feature)", r"after (the )?(recent |latest |new )?update",
            r"old (version|app|ui)", r"bring (back|the old)", r"\bui\b", r"\bux\b", r"user ?-?friendly", r"confus",
            r"(extra|more|one more|multiple) (click|tap|step|hit)", r"seat ?-?belt", r"seat buckle", r"simplif",
            r"update (made|is) (it )?wors",
        ],
    },
    {
        "id": "booking_flow",
        "label": "Booking / cancel / edit / no-show rules",
        "owner": "product",
        "patterns": [
            "(unable|not able|can'?t|cannot) (to )?schedule", 'schedules? (are |is )?not (being )?(show|list|visible)', 'booked schedules?', 'amendment', 'address', '\\bqr\\b', 'calendar',
            r"(unable|not able|can'?t|cannot|couldn'?t) (to )?(book|cancel|edit|change|modify|amend|reschedul)",
            r"no (option|way) (to|for) (cancel|edit|change|book|modify)", r"wait ?-?list", r"no ?-?show",
            r"cut ?-?off", r"roster", r"ad ?-?hoc", r"(wrong|different) date", r"edit options?", r"cancel\w* (the ride|by itself|my)", r"duplicate (schedule|booking)",
            r"booking (fail|issue|problem|error|difficult)", r"not booked", r"(change|update) (the |my )?(address|location)",
        ],
    },
    {
        "id": "performance",
        "label": "Slow / loading / freezes",
        "owner": "app",
        "patterns": [r"\bslow", r"loading", r"\bhang", r"freez", r"\blag", r"stuck", r"takes? (forever|too much time|so long)"],
    },
    {
        "id": "routing_pooling",
        "label": "Long routes / bad pooling",
        "owner": "service",
        "patterns": [
            r"routing", r"(wrong|longer?|bad|worst|incorrect) routes?", r"routes? (is|are) (very |too )?(long|bad|wrong)", r"club(bing|bed)?", r"pool(ing)?", r"(\d|two|three|2\.5) ?(hours?|hrs?) (to|for) (reach|travel)",
            r"longest", r"long (route|way|time in)", r"pick ?-?up (point|location) (is )?far", r"nodal point", r"middle of nowhere",
        ],
    },
    {
        "id": "cab_delay",
        "label": "Cab late / not assigned / no-show by vendor",
        "owner": "service",
        "patterns": [
            r"\blate\b", r"(cab|vehicle|bus|pickup|drop|trip) (is |was |gets |getting )?delay", r"delayed", r"not (been )?(assigned|allocated|allotted)", r"(never|didn'?t|did not) (come|arrive|show)",
            r"wait(ed|ing)? (for )?(more than |over )?\d+", r"allocation", r"(cab|vehicle|bus|driver) (is |was )?(always |never )?(late|on time)",
            r"pick ?-?up time", r"timing",
        ],
    },
    {
        "id": "driver_behavior",
        "label": "Driver behaviour",
        "owner": "service",
        "patterns": [
            r"driver\w* (are |is |was |were )?(very |so |extremely )?(rude|abusive|unprofessional|misbehav|shout|rash|drunk|careless)",
            r"(rude|abusive|unprofessional|rash) driver", r"misbehav", r"driving (is )?(rash|bad|dangerous)",
        ],
    },
    {
        "id": "no_feedback_channel",
        "label": "No in-app way to give feedback / complaints ignored",
        "owner": "product",
        "patterns": [
            r"no (feedback|complain)\w* (option|link|button|section)", r"(doesn'?t|does not|don'?t) allow (any )?feedback",
            r"(can'?t|cannot|unable to) (even )?(write|give|submit) (in )?(the )?(built in )?feedback",
            r"(answer|response|reply) (for|to) (a |my )?(bad )?feedback", r"(don'?t|doesn'?t|not) listen to feedback",
            r"reported the issue,? but no", r"feedback (option|link) for (the )?app",
        ],
    },
    {
        "id": "driver_contact",
        "label": "Calling / chatting with driver",
        "owner": "app",
        "patterns": [
            r"(audio|voice|call) (is )?(not )?(clear|audible)", r"chat", r"messag\w* (feature|option|driver)",
            r"calling permission", r"(contact|call|reach) (the )?driver", r"masked (number|call)", r"mobile number is not visible",
        ],
    },
    {
        "id": "safety",
        "label": "Safety concern",
        "owner": "service",
        "patterns": [r"\bunsafe", r"safety", r"\bfemale", r"\bwomen", r"\bgirl", r"\bsos\b", r"harass", r"escort", r"\bguard\b"],
    },
    {
        "id": "support",
        "label": "Helpdesk / support unreachable",
        "owner": "service",
        "patterns": [
            r"help ?-?desk", r"support", r"customer (care|service)", r"helpline", r"sahayta|saheta", r"\bivr\b",
            r"(not|never|no one|nobody) (is )?(picking|pick|answering|respond)\w*", r"(not|n'?t) (receiving|receive|pick\w*|answer\w*) (the |my |our )?calls?", r"transport (team|desk|management)",
            r"no response", r"(complain|concern)\w* (are |is )?(ignor|not)",
        ],
    },
]

# Catch-all for reviews that blame the transport service as a whole, without a specific issue.
SERVICE_GENERAL = {
    "id": "service_general",
    "label": "General service complaint (unspecific)",
    "owner": "service",
    "patterns": [r"service", r"transport", r"management", r"vendor", r"facilit", r"company", r"cabs?", r"monopoly"],
}
THEMES.append(SERVICE_GENERAL)

_COMPILED = [(t["id"], [re.compile(p, re.I) for p in t["patterns"]]) for t in THEMES]
THEME_BY_ID = {t["id"]: t for t in THEMES}


def classify(text):
    """Return the list of theme ids that match this review."""
    if not text:
        return []
    hits = [tid for tid, pats in _COMPILED if any(p.search(text) for p in pats)]
    # The Play-Store lockout is a specific kind of "won't open"; don't double count it.
    if "integrity_block" in hits and "crash_wont_open" in hits:
        hits.remove("crash_wont_open")
    # The catch-all only applies when nothing specific matched.
    if "service_general" in hits and len(hits) > 1:
        hits.remove("service_general")
    return hits
