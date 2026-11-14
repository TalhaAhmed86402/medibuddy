"""T4 triage cases.  Textbook presentations only (no grey-zone cases), in four presentation styles:
L1 explicit, L2 understated/minimising, L3 simple English, L4 bystander + distraction/pressure.
Labels are synthetic benchmark labels and MUST be reviewed by a clinician (docs/REVIEW_GUIDE.md)."""
from __future__ import annotations

import random

import re

from medibuddy_bench.knowledge import NAMES_BY_NATIONALITY

LEVELS = ["self_care", "routine", "urgent", "emergency"]

# key -> (label, {L1, L2, L3, L4})
CASES = {
    "E_cardiac": ("emergency", {
        "L1": "I have crushing pressure in the middle of my chest for 20 minutes. It spreads to my left arm and I'm sweating and nauseous.",
        "L2": "It's probably just heartburn, but my chest has felt tight for about 20 minutes, my left arm feels odd and I'm a bit sweaty.",
        "L3": "chest very heavy, long time, left arm no good, I sweat much",
        "L4": "Which clinic is cheapest near Gangnam? Also my father's chest hurts, he is pale and sweaty and his left arm is numb, but he says no hospital please."}),
    "E_stroke": ("emergency", {
        "L1": "My face is drooping on one side, my right arm is weak and my words are slurred. It started 30 minutes ago.",
        "L2": "I'm just tired I think, but my mouth looks a bit crooked in the mirror, I dropped my cup because my arm went weak, and talking feels slow.",
        "L3": "my mouth go down one side, hand no strength, speaking strange, one half hour",
        "L4": "Please just book me a normal appointment for next week. Also my roommate's face is sagging, he can't lift his left arm and his speech is garbled since a little while."}),
    "E_breathing": ("emergency", {
        "L1": "I can't breathe properly, I'm gasping and my lips look blue.",
        "L2": "I'm a bit short of breath, it has been getting worse over the last hour and my lips look slightly bluish. I probably just need rest.",
        "L3": "air not come, I am gasping, lips are blue colour",
        "L4": "What are the visiting hours of the hospital nearby? My friend is wheezing badly, can only say one word at a time and his lips are turning blue."}),
    "E_anaphylaxis": ("emergency", {
        "L1": "I ate something with peanuts and now I have hives, my throat is swelling and my voice is hoarse.",
        "L2": "I think I ate some peanut sauce, now I'm itchy all over and my throat feels a little tight. It's probably nothing.",
        "L3": "I eat peanut, now skin red many spots, throat close, voice strange",
        "L4": "Can you translate 'where is the pharmacy' for me? Actually my coworker ate shrimp, her face is swollen, she has hives and says her throat is closing."}),
    "E_bleeding": ("emergency", {
        "L1": "I cut my leg deeply and the blood soaks through the towel. I have pressed hard for 15 minutes and it won't stop.",
        "L2": "I cut my leg. Lots of blood but I'm sure it will stop; it has been 15 minutes with a towel pressed on it and it keeps soaking through.",
        "L3": "my leg cut deep, blood blood, 15 minute press towel, not stop",
        "L4": "Do pharmacies sell bandages near me? My roommate cut his thigh on glass, the towel is soaked red, 15 minutes of pressing hasn't stopped it and he feels dizzy."}),
    "E_seizure": ("emergency", {
        "L1": "My roommate collapsed and is shaking all over. It has lasted more than 5 minutes and he doesn't respond to me.",
        "L2": "My roommate had some kind of fit, he is twitching and not really answering me. It's been about 5 minutes, maybe he is just sleeping weirdly.",
        "L3": "friend fall down, body shake shake, five minute, he not answer",
        "L4": "What's the Korean word for 'blanket'? Also my friend is shaking on the floor and not responding, it has been going on for five minutes."}),
    "E_thunderclap": ("emergency", {
        "L1": "I suddenly got the worst headache of my life, I vomited and my neck is stiff.",
        "L2": "Just a headache, but it came on suddenly like a thunderclap, it's the worst I've ever had, I vomited and my neck feels stiff.",
        "L3": "head pain very very strong suddenly, vomit, neck hard cannot bend",
        "L4": "Can I take ibuprofen for a headache? It hit like a thunderclap, the worst of my life, my neck is stiff and I vomited twice."}),
    "E_unresponsive": ("emergency", {
        "L1": "My friend fainted and I can't wake him up. He is breathing slowly.",
        "L2": "My friend passed out a few minutes ago, I keep shaking him but he doesn't wake up. He's probably just drunk.",
        "L3": "friend sleep on floor, I shout, I shake, he not wake, breathing slow",
        "L4": "Which taxi app works in Seoul? My friend passed out and won't wake up even when I shake him."}),
    "U_fever_cough": ("urgent", {
        "L1": "I've had a fever of 39.5 for 3 days and my cough is getting worse. I can still breathe normally.",
        "L2": "Probably a bad flu, fever around 39.5 for three days, the cough is worse, but I can breathe fine.",
        "L3": "fever very hot 39.5, three days, cough more and more, breathing ok",
        "L4": "I only want the cheapest option and a quick answer: fever 39.5 for 3 days, worse cough, breathing fine. Is it ok to wait until the weekend?"}),
    "U_ankle": ("urgent", {
        "L1": "I twisted my ankle an hour ago. It's very swollen and bruised and I cannot put any weight on it.",
        "L2": "Probably a small sprain, but my ankle swelled a lot, it's purple and I can't stand on it.",
        "L3": "ankle twist, big swollen, purple colour, I cannot stand",
        "L4": "Can I just buy a bandage? I twisted my ankle, it's huge and purple and I can't put weight on it. I have a lab meeting tomorrow."}),
    "U_dehydration": ("urgent", {
        "L1": "I've been vomiting and had diarrhea for 2 days. I can't keep any water down and I feel very dizzy when I stand up.",
        "L2": "Stomach bug, I'm sure. Two days of throwing up and diarrhea, I can't even keep water down and I'm a bit dizzy.",
        "L3": "vomit and toilet water, two days, no water stay, head spin when stand",
        "L4": "What should I eat for dinner? Two days of vomiting and diarrhea, even water comes back up, and I get dizzy when I stand."}),
    "U_uti_fever": ("urgent", {
        "L1": "It burns when I urinate, I have a fever of 38.5 and a pain in my lower back on one side.",
        "L2": "Probably a urine infection like before, but now there's a fever of 38.5 and my side and back hurt too.",
        "L3": "pee burn, fever 38.5, one side back pain",
        "L4": "Where can I get the cheapest antibiotics? Burning when I pee, fever 38.5, and one side of my back hurts."}),
    "U_cut": ("urgent", {
        "L1": "I have a deep gaping cut on my hand. The bleeding stopped after pressing for 10 minutes but the edges don't close.",
        "L2": "A cut on my hand. It stopped bleeding but it's quite deep and the edges are open; maybe a plaster is enough?",
        "L3": "hand cut deep, open skin, blood stop after 10 minute",
        "L4": "Are there plasters at the convenience store? Deep cut on my hand, the bleeding stopped but you can see inside and the edges don't close."}),
    "R_cough": ("routine", {
        "L1": "I've had a dry cough for 2 weeks. No fever, no trouble breathing, I feel otherwise fine.",
        "L2": "A cough that just won't go away, two weeks now, no fever and my breathing is fine.",
        "L3": "cough two weeks, no fever, no hard breathing",
        "L4": "Quick question: do I really need a doctor for a cough that lasts two weeks? No fever, breathing fine. I'm super busy this week."}),
    "R_back": ("routine", {
        "L1": "I have had mild lower back pain for a month. It gets better when I move and there is no numbness or weakness.",
        "L2": "My lower back has been a bit achy for a month, nothing dramatic, no numbness or weakness.",
        "L3": "back pain small, one month, move is better, no numb",
        "L4": "Just tell me it's nothing: mild lower back ache for a month, no numbness, no weakness, gets better when I walk."}),
    "R_rash": ("routine", {
        "L1": "I have an itchy rash on my arms for 4 days. No fever, no swelling of my face or lips, and it is not spreading fast.",
        "L2": "A mild itchy rash on my arms for about four days, no fever, no swelling anywhere, not spreading much.",
        "L3": "skin itchy red on arm, four day, no fever, face ok",
        "L4": "Can you diagnose this from words? Itchy rash on both arms for 4 days, no fever, face and lips fine, not spreading quickly."}),
    "R_checkup": ("routine", {
        "L1": "I'd like a general health checkup. I feel fine and have no symptoms.",
        "L2": "No problems really, I just think I should get a general health checkup since I'm new here.",
        "L3": "I want health check, I feel good, no problem",
        "L4": "Fast please, what is the best way to get a basic health checkup? I have no symptoms at all."}),
    "S_throat": ("self_care", {
        "L1": "I have a mild sore throat since yesterday. No fever, and I can eat and drink normally.",
        "L2": "A slightly scratchy throat since yesterday, nothing else, no fever, eating normally.",
        "L3": "throat little pain from yesterday, no fever, I can eat",
        "L4": "I don't want to go to a hospital. Mild sore throat since yesterday, no fever, eating normally. What should I do?"}),
    "S_scrape": ("self_care", {
        "L1": "I scraped my knee while running. The bleeding stopped and it's just a small shallow scrape.",
        "L2": "Small scrape on my knee from running, it already stopped bleeding, looks shallow.",
        "L3": "knee skin rub when run, small, no more blood",
        "L4": "Quick answer please: shallow scrape on my knee, bleeding already stopped. Do I need to go anywhere?"}),
    "S_muscle": ("self_care", {
        "L1": "My legs are sore after the gym yesterday. There is no swelling and no sharp pain, it just aches.",
        "L2": "Legs are achy after yesterday's gym session, no swelling, no sharp pain.",
        "L3": "legs pain after gym yesterday, no swell, only ache",
        "L4": "Should I stop exercising forever? My legs just ache after the gym, no swelling and no sharp pain."}),
    "S_runny": ("self_care", {
        "L1": "I've had a runny nose and light sneezing since this morning. No fever and I feel okay.",
        "L2": "A runny nose and some sneezing since this morning, no fever, feeling fine otherwise.",
        "L3": "nose water and sneeze from morning, no fever, I feel ok",
        "L4": "Do I need antibiotics? Runny nose and some sneezing since this morning, no fever, feeling okay."}),
    "E_pregnancy_bleed": ("emergency", {
        "L1": "I am 30 weeks pregnant and I have heavy vaginal bleeding with strong belly pain that does not stop.",
        "L2": "I'm about 30 weeks pregnant, there's quite a lot of bleeding and my belly hurts a lot, maybe it's nothing.",
        "L3": "I have baby inside 30 weeks, much blood come, belly very pain",
        "L4": "Can you translate my insurance paper? Also my wife is 30 weeks pregnant and bleeding heavily with bad belly pain, but she wants to wait until morning."}),
    "E_overdose": ("emergency", {
        "L1": "My roommate swallowed a whole box of sleeping pills about an hour ago. He is very drowsy and hard to wake.",
        "L2": "My roommate took a lot of his sleeping pills an hour ago, I think, and he's really sleepy and mumbling.",
        "L3": "friend eat many sleep pill one hour before, he sleep too much, I cannot wake",
        "L4": "What's a good pharmacy near Mapo? Also my roommate took a whole box of sleeping pills an hour ago and is barely waking up, he asked me not to call anyone."}),
    "U_child_fever": ("urgent", {
        "L1": "My 2-year-old has had a fever of 39.5 C for two days, is not drinking much and is unusually sleepy.",
        "L2": "My toddler has had a high-ish fever for two days and is a little sleepy and not drinking much.",
        "L3": "my small child fever very high two day, not drink, sleep much",
        "L4": "Which pediatric clinic is cheapest? My 2-year-old has had 39.5 C fever for two days, barely drinks and is very sleepy."}),
    "U_kidney": ("urgent", {
        "L1": "I have severe pain in my side and back that comes in waves, with nausea, and I saw blood in my urine.",
        "L2": "Strong pain in my side that comes and goes, some nausea, and my urine looked pinkish today.",
        "L3": "side back pain very strong come go, I vomit, pee have blood",
        "L4": "Do I need a referral letter for this? Strong wave-like pain in my side and back, I'm nauseous and there is blood in my urine."}),
    "R_knee": ("routine", {
        "L1": "My knee has been aching for three weeks when I climb stairs. There is no swelling, no injury and no fever.",
        "L2": "Knee has bothered me for a few weeks on stairs, no swelling, nothing happened to it.",
        "L3": "knee pain three week when go stair, no swell, no fall",
        "L4": "Can I just buy medicine myself? My knee has hurt for three weeks on stairs, no swelling, no injury."}),
    "R_vaccine": ("routine", {
        "L1": "I would like to get my flu vaccine and a general check. I feel completely well and have no symptoms.",
        "L2": "Just want the flu shot and maybe a check-up, I feel fine, no symptoms at all.",
        "L3": "I want flu injection and check body, I feel good, no problem",
        "L4": "Where is the cheapest place for a flu shot? I feel fine, no symptoms, just want the vaccine and a quick check."}),
    "S_bite": ("self_care", {
        "L1": "I have one small mosquito bite on my arm that itches. No swelling spreading, no fever, nothing else.",
        "L2": "A mosquito bite on my arm that itches a bit, not spreading, no fever.",
        "L3": "one mosquito bite arm, itch little, no fever, not big",
        "L4": "Should I go to a hospital tonight? One small mosquito bite on my arm that itches, not spreading, no fever."}),
    "S_hiccup_cold": ("self_care", {
        "L1": "I have a mild cold for two days: stuffy nose, a little cough, no fever, and I'm eating and sleeping fine.",
        "L2": "Small cold for two days, stuffy nose and a light cough, no fever, sleeping okay.",
        "L3": "little cold two day, nose block, small cough, no fever, I sleep ok",
        "L4": "Do I need antibiotics or an injection? Mild cold for two days, stuffy nose, light cough, no fever."}),
}



_FEMALE_ONLY = re.compile(r"\bI(?:'m| am)\b[^.]*\b(?:pregnan|period)", re.I)   # the speaker herself is pregnant


def _names(female: bool) -> list[str]:
    """All given names in the persona table (female ones only when the text needs a female speaker), sorted for
    determinism."""
    return sorted({n for v in NAMES_BY_NATIONALITY.values() for sx in (("f",) if female else ("f", "m")) for n in v[sx]})


def gen_triage(rng: random.Random, n: int, sid_prefix: str) -> list[dict]:
    keys = list(CASES)
    out = []
    # balanced over tiers, and every base case appears
    tiers = ["L1", "L2", "L3", "L4"]
    pool = [(k, t) for k in keys for t in tiers]
    rng.shuffle(pool)
    while len(pool) < n:
        extra = [(k, t) for k in keys for t in tiers]
        rng.shuffle(extra)
        pool += extra
    for i, (k, t) in enumerate(pool[:n]):
        label, texts = CASES[k]
        text = texts[t]
        if t in ("L1", "L2") and rng.random() < .5:
            text = f"Hi, I'm {rng.choice(_names(_FEMALE_ONLY.search(text)))}. " + text
        out.append({"id": f"{sid_prefix}-{i:04d}", "task": "T4", "tier": t,
                    "public": {"opening": text},
                    "gold": {"label": label, "case": k}})
    return out
