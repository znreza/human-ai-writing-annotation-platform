"""Study content: the merged category set (used in both stages), the rating options, and the
briefing/consent text. Kept in one place so the design can be revised without touching app logic.

Stage 2 shows the merged category set: common edit types grouped by family, plus a genre-specific group
drawn from our LLM judge's checklist (checklist_templates.json). Given the conversation, it asks whether
each change was asked or implied by the user.
"""

# ---- rating options (radio dials, consistent across stages) ----
PRESENCE_OPTIONS = ["Absent", "Present", "Very present"]                       # Stage 2
JUSTIFY_OPTIONS = ["Asked", "Implied", "Not asked or implied", "Unsure"]      # Stage 2

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
    "General": [
        ("length_expansion", "Expansion", "Made the piece noticeably longer overall."),
        ("length_compression", "Compression", "Made the piece noticeably shorter overall."),
        ("overall_polish", "Overall polish", "General smoothing or polishing across the piece."),
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

# ---- which categories require written evidence (details/remarks referring to line numbers) ----
# Groups whose categories require evidence when the annotator marks them Present / Very present.
# Other groups only invite optional remarks. "Genre-specific categories" is the synthetic group
# name appended by categories_for().
DETAIL_REQUIRED_GROUPS = {"Style and register", "Meaning and content",
                          "Personal voice", "Genre-specific categories"}
# Within a required group, these category ids stay optional.
DETAIL_OPTIONAL_EXCEPTIONS = {"formality"}

def detail_required(group_name, cid):
    """True if this category should require written evidence referring to line numbers."""
    return group_name in DETAIL_REQUIRED_GROUPS and cid not in DETAIL_OPTIONAL_EXCEPTIONS

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
## Before you begin

You will compare **12 pairs** of short texts across three kinds of writing: **fiction, academic
writing, and job applications**. In each pair, one text is an author's original draft and the other is
a revised version of it. The study has **two short stages**, shown one at a time.

**Please do not use any AI or LLM tools at any point during this task** (ChatGPT, Claude, Gemini, or any
writing assistant). We want your own observations in your own words. All responses are screened by an
AI-detection tool, and **responses detected as AI-generated will not be compensated.**
"""

CONSENT_FORM = """
## Adult Consent Form

#### TITLE OF RESEARCH: Study on Human Writing

#### PRINCIPAL INVESTIGATOR: Marwa Abdulhai

#### PRINCIPAL INVESTIGATOR’S DEPARTMENT: Computer Science

You are being invited to take part in a research study. Before you decide to participate in this study, it is important that you understand why the research is being done and what it will involve. Please take the time to read the following information carefully. Please ask the researcher if there is anything that is not clear or if you need more information.

**Purpose of the research:**

This project aims to collect data that can be used to understand the types of edits made to written text.

**Study Procedures:**

If you agree to be in this study, you will be shown a series of paired texts in an online interface. In each pair, one text is an author's original draft, and the other is a revised version of it. For each pair, you will be asked to identify the differences between the two versions and answer follow up questions about the differences. You will respond using short written answers and multiple-choice selections.

The answers you provide in the task may be used as stimuli for future participants. However, data that would identify you will not be shared with other participants.

The study duration will vary from 5 to 30 minutes. 


**Benefits and Risks:**

There are no direct benefits to you as a participant; however, by furthering our understanding of edits made to pieces of writing, this research will benefit society by helping develop better tools for assisting people in writing tasks.

Risks associated with participation in this study are minimal. As with all research, there is the risk of an unintended breach of confidentiality. However, we are taking precautions to minimize this risk (see below).


**Confidentiality:**

We will not be asking for any personally identifying information, and we will handle responses as confidentially as possible. Your name, or your Worker IDs will never be tied to your responses on this survey. However, we cannot guarantee the confidentiality of information transmitted over the Internet. To minimize this risk, data containing anything that might be personally identifiable (e.g. Worker IDs) will be encrypted on transfer and storage and will only be accessible to qualified lab personnel. We will be keeping data collected as part of this experiment indefinitely. This anonymized data (containing neither Worker IDs nor IP addresses) may be shared with the scientific community and corporate sponsors. At the end of the survey you may be asked if you would like to provide your email or Prolific ID to be contacted to participate in future studies., If you choose to provide this information, you may be contacted for participation in future studies.


**Compensation:**

For your participation, you will receive $10/hr for your participation. If you are on Prolific and for any reason you do not complete the study (e.g. technical difficulties, or a desire to stop), we will only be able to pay you if you send an email through Prolific, or by emailing the researcher, at marwa_abdulhai@berkeley.edu.  If you have any questions about the study, feel free to contact the researcher or the Principal Investigator, Marwa Abdulhai, at marwa_abdulhai@berkeley.edu.   

Who to contact with questions:

1.	PRINCIPAL INVESTIGATOR:

            Marwa Abdulhai
            marwa_abdulhai@berkeley.edu

2.	If you have questions regarding your rights as a research subject, or if problems arise which you do not feel you can discuss with the Investigator, please contact the Institutional Review Board at:

            Assistant Director, Research Integrity and Assurance
            Phone: (609) 258-8543
            Email: irb@princeton.edu

3.	I understand the information that was presented and that:

	A.	My participation is voluntary, and I may withdraw my consent and discontinue participation in the project at any time.  My refusal to participate will not result in any penalty.

	B.	I do not waive any legal rights or release Princeton University, its agents, or you from liability for negligence.

4.	I hereby give my consent to be the subject of your research.  

_You should save a copy of this consent form for your records._

If you wish to participate in this study, please click the **"I consent"** button below.
"""
