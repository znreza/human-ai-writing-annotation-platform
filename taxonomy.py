"""Study content: the merged category set (used in both stages), the rating options, and the
briefing/consent text. Kept in one place so the design can be revised without touching app logic.

Both stages show the SAME categories: common edit types grouped by family, plus a genre-specific group
drawn from our LLM judge's checklist (checklist_templates.json). Stage 2 rates how present each is in the
revision; Stage 3 asks, given the conversation, whether each was asked or implied by the user.
"""

# ---- rating options (radio dials, consistent across stages) ----
PRESENCE_OPTIONS = ["Absent", "Present", "Very present"]                       # Stage 2
JUSTIFY_OPTIONS = ["Asked", "Implied", "Not asked or implied", "Unsure"]      # Stage 3

# ---- common edit types, grouped (id, label, definition) ----
EDIT_GROUPS = {
    "Grammar and mechanics": [
        ("spelling_punctuation", "Spelling and punctuation", "Corrected spelling, punctuation, or capitalization."),
        ("grammar_syntax", "Grammar and syntax", "Fixed grammatical errors or awkward syntax."),
        ("tense_agreement", "Tense and agreement", "Made verb tense or subject-verb agreement consistent."),
    ],
    "Sentence level": [
        ("word_choice", "Word choice and diction", "Replaced words with different or more advanced vocabulary."),
        ("sentence_structure", "Sentence structure", "Split, combined, or reordered words within sentences."),
        ("conciseness", "Conciseness and clarity", "Tightened wordiness or made sentences clearer."),
        ("sentence_variety", "Sentence variety and rhythm", "Varied sentence length or cadence."),
    ],
    "Structure and organization": [
        ("paragraphing", "Paragraphing", "Changed paragraph breaks or grouping."),
        ("ordering", "Ordering of ideas", "Reordered ideas, events, or sections."),
        ("formatting", "Formatting and layout", "Changed headings, lists, or visual layout."),
        ("transitions", "Transitions", "Added or changed transitions and connectives."),
    ],
    "Style and register": [
        ("formality", "Formality and register", "Made the writing more formal or more casual."),
        ("tone", "Emotional tone", "Shifted the emotional tone of the piece."),
        ("emotional_range", "Emotional range", "Widened the range of emotions or made the affect more dynamic, versus a flat, monotone, single affect."),
        ("figurative", "Figurative language", "Added metaphors, imagery, or descriptive flourish."),
        ("sensory_detail", "Sensory or concrete detail", "Added sensory detail or concrete specifics."),
    ],
    "Meaning and content": [
        ("added_content", "Added content", "Introduced new ideas, events, or information."),
        ("removed_content", "Removed content", "Deleted ideas or information the author wrote."),
        ("factual_change", "Changed facts or specifics", "Altered facts, names, numbers, or claims."),
        ("resolution", "Resolved the open", "Closed a question or conflict the author left open."),
        ("theme_moral", "Made theme or moral explicit", "Spelled out a theme, message, or moral."),
        ("sanitize", "Sanitized or softened", "Softened or removed dark, risky, or explicit content."),
        ("intention_shift", "Shifted the intention", "Changed what the author was trying to say or do."),
    ],
    "Personal voice": [
        ("voice_flattening", "Flattened distinctive voice", "Made the writing read less like this particular author."),
        ("idiosyncrasy_removed", "Removed idiosyncrasy", "Removed quirks, personal phrasing, or imperfections."),
        ("stance_change", "Changed stance or perspective", "Altered the author's viewpoint or attitude."),
        ("authenticity", "Reduced authenticity", "Made emotionally authentic writing feel generic."),
    ],
    "General": [
        ("length_expansion", "Expansion", "Made the piece noticeably longer overall."),
        ("length_compression", "Compression", "Made the piece noticeably shorter overall."),
        ("overall_polish", "Overall polish", "General smoothing or polishing across the piece."),
    ],
}

# ---- genre-specific categories (from the judge checklist; duplicates of the common groups removed) ----
GENRE_SPECIFIC = {
    "fiction": [
        ("past_tense", "Past-tense narration", "Narration is in consistent past tense."),
        ("scene_not_summary", "Scene, not summary", "Events are dramatized as a rendered scene rather than told as summary."),
        ("named_setting", "Named setting or characters", "Named characters and/or a specified, concrete setting."),
        ("direct_dialogue", "Direct dialogue", "Direct quoted dialogue or spoken lines."),
        ("arc_closure", "Arc and closure", "A shaped arc with an explicit resolution or satisfying closure."),
        ("neutral_voice", "Neutral literary voice", "Absence of an idiosyncratic or sardonic narrator or direct second-person address to the reader."),
    ],
    "academic": [
        ("hedging", "Hedging", "Hedged, qualified claims (may, suggests, likely, appears to)."),
        ("nominalization", "Nominalization", "Nominalized, abstract phrasing (the implementation of, the utilization of)."),
        ("standard_citations", "Standard citations", "Author-date or otherwise standardized citation formatting."),
        ("tidy_conclusion", "Tidy conclusion", "An explicit concluding restatement, synthesis, or recommendations."),
        ("interpretive_framing", "Interpretive framing", "Added interpretation, critique, or normative framing beyond the raw factual content."),
        ("reduced_empirical", "Reduced empirical specificity", "Absence or reduction of concrete numeric, empirical, or measurement detail."),
    ],
    "application": [
        ("salutation_closing", "Salutation and closing", "Standard salutation (Dear...) and/or professional sign-off or closing."),
        ("persuasive_framing", "Persuasive framing", "Persuasive, self-promotional reframing of experience rather than plain listing."),
        ("generic_soft_skills", "Generic soft skills", "Generic soft-skill or competency language (team player, results-driven, strong communicator)."),
        ("targeted_framing", "Targeted framing", "Explicitly targets a specific role, company, or audience."),
        ("placeholders", "Placeholders or boilerplate", "Contact or detail placeholders or boilerplate scaffolding (e.g. [Your Name], [Company])."),
        ("reduced_specifics", "Reduced concrete specifics", "Absence or reduction of concrete metrics, numbers, named tools, or quantitative detail."),
    ],
}

# genres without their own set map to the closest available one
GENRE_MAP = {"fiction": "fiction", "script": "fiction", "poetry": "fiction",
             "academic": "academic", "application": "application", "correspondence": "application"}

def categories_for(genre):
    """Ordered list of (group_name, [(id, label, help), ...]) shown in BOTH stages for this genre."""
    groups = list(EDIT_GROUPS.items())
    gs = GENRE_SPECIFIC.get(GENRE_MAP.get(genre, "fiction"), [])
    groups.append(("Genre-specific categories", gs))
    return groups

# flat lookup: id -> (label, help)
def _flat():
    out = {}
    for _, items in EDIT_GROUPS.items():
        for eid, label, hlp in items:
            out[eid] = (label, hlp)
    for _, items in GENRE_SPECIFIC.items():
        for eid, label, hlp in items:
            out[eid] = (label, hlp)
    return out
CATEGORY_LOOKUP = _flat()

# ---- Stage 0: study rules (keep the no-LLM warning) + the formal IRB consent form ----
STUDY_RULES = """
### Before you begin

You will compare **12 pairs** of short texts across three kinds of writing: **fiction, academic
writing, and job applications**. In each pair, one text is an author's original draft and the other is
a revised version of it. The study has **three short stages**, shown one at a time.

**Please do not use any AI or LLM tools at any point during this task** (ChatGPT, Claude, Gemini, or any
writing assistant). We want your own observations in your own words. All responses are screened by an
AI-detection tool, and **responses detected as AI-generated will not be compensated.**
"""

CONSENT_FORM = """
### Consent Form for Investigating the Impact of AI on Writing

**Introduction**

My name is Dr. Marwa Abdulhai. I am a postdoctoral fellow at Princeton University, in the Department of Computer Science. I am planning to conduct a research study,
which I invite you to take part in.

**Purpose**

The purpose of this study is to collect data in order to understand what people think is deceptive or not.

**Procedures**

If you agree to be in this study, you will be asked to view some interactions in an interface and answer
whether each interaction is deceptive or not on a scale.

Study time: The estimated study completion time has been displayed to you in CloudResearch Connect interface.

Study location: You will participate online, from the comfort of your current location.

**Benefits**

There is no direct benefit to you (other than compensation) from participating in this study. We hope that
the information gained from the study will help us design better methods to mitigate deception.

**Risks/Discomforts**

This study represents minimal risk to you. As with all research, there is the risk of an unintended breach
of confidentiality. However, we are taking precautions to minimize this risk (see below).

**Confidentiality**

The data we collect will be stored on password-protected servers. Once the research is complete, we intend
to scrub the data of all identifiable information. We will keep only the recorded survey responses, as well
as a freshly generated identifier for each subject. The de-identified data will be retained indefinitely for
possible use in future research done by ourselves or others. This cleaned dataset may be made public as part
of the publishing process. No guarantees can be made regarding the interception of data sent via the Internet
by any third parties.

**Compensation**

We compensate workers based on the estimated duration of completing the study. The study will be prorated to
$20/hour for the anticipated duration of completing the study, which is posted for your job on the
CloudResearch interface you used to view the job (duration includes reviewing instructions, completing the
task, and filling an exit survey). The payment is arranged by CloudResearch via credit to subjects' accounts.

**Rights**

Participation in research is completely voluntary. You have the right to decline to participate or to withdraw
at any point in this study without penalty or loss of benefits to which you are otherwise entitled.

**Questions**

If you have any questions or concerns about this study, or in case anything goes wrong with the online
interface, you can contact Marwa Abdulhai at marwa_abdulhai@berkeley.edu. If you have any questions or concerns
about your rights and treatment as a research subject, you may contact the office of UC Berkeley's Committee
for the Protection of Human Subjects, at 510-642-7461 or subjects@berkeley.edu.

**IRB review:**

This study was approved by an IRB review under the CPHS protocol ID number 2022-07-15514.

_You should save a copy of this consent form for your records._

If you wish to participate in this study, please click the **"I consent"** button below.
"""
