"""
ReViewSense AI — Seed Data Generator
=====================================
Creates a demo company with 12 agents, 200+ realistic call records,
analyses, live sessions, and tags — ready for a live presentation.

Usage:
    cd backend
    python seed_data.py

Idempotent: drops existing demo data before re-seeding.
"""

import sys, os, random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from database import engine, Base, SessionLocal
from auth import hash_password
import models

# ── Config ────────────────────────────────────────────────────────────────────
DEMO_COMPANY    = "TechCo Solutions"
DEMO_EMAIL      = "admin@techco.com"
DEMO_PASSWORD   = "demo1234"
NUM_CALLS       = 220
WEEKS_OF_DATA   = 8          # spread calls across this many weeks

# ── Reference data ────────────────────────────────────────────────────────────
AGENTS = [
    ("AG-001", "Sarah Mitchell",   "sarah@techco.com",  "Customer Support", "morning"),
    ("AG-002", "James Okafor",     "james@techco.com",  "Customer Support", "morning"),
    ("AG-003", "Priya Sharma",     "priya@techco.com",  "Technical Support","afternoon"),
    ("AG-004", "Carlos Rivera",    "carlos@techco.com", "Billing",          "afternoon"),
    ("AG-005", "Emily Zhang",      "emily@techco.com",  "Customer Support", "night"),
    ("AG-006", "David Kim",        "david@techco.com",  "Technical Support","morning"),
    ("AG-007", "Marcus Webb",      "marcus@techco.com", "Customer Support", "afternoon"),
    ("AG-008", "Lisa Nguyen",      "lisa@techco.com",   "Billing",          "night"),
    ("AG-009", "Ahmed Hassan",     "ahmed@techco.com",  "Technical Support","morning"),
    ("AG-010", "Rachel Cooper",    "rachel@techco.com", "Customer Support", "afternoon"),
    ("AG-011", "Tomás Fernández",  "tomas@techco.com",  "Customer Support", "morning"),
    ("AG-012", "Aisha Patel",      "aisha@techco.com",  "Technical Support","night"),
]

# Agent skill tiers — affects score distribution
AGENT_TIERS = {
    "AG-001": "top",    "AG-002": "top",    "AG-003": "good",
    "AG-004": "good",   "AG-005": "mid",    "AG-006": "good",
    "AG-007": "low",    "AG-008": "low",    "AG-009": "mid",
    "AG-010": "good",   "AG-011": "mid",    "AG-012": "top",
}

TIER_SCORE_RANGE = {
    "top":  (82, 98),
    "good": (68, 88),
    "mid":  (55, 78),
    "low":  (35, 62),
}

ISSUES = [
    ("Billing Issue",      0.20),
    ("Technical Problem",  0.18),
    ("Account Access",     0.14),
    ("Service Outage",     0.10),
    ("Refund Request",     0.12),
    ("Product Inquiry",    0.10),
    ("Subscription Change",0.06),
    ("Data Privacy",       0.04),
    ("General Inquiry",    0.06),
]

EMOTIONS       = ["Calm", "Frustrated", "Angry", "Confused", "Satisfied", "Concerned", "Impatient", "Disappointed"]
RESOLUTIONS    = ["Resolved", "Partially Resolved", "Not Resolved"]
SENTIMENTS     = ["Positive", "Neutral", "Negative"]
CALL_TYPES     = ["inbound", "outbound"]
SOURCES        = ["upload", "live", "ai_agent"]
TAGS_POOL      = ["escalation", "first-contact", "follow-up", "vip", "refund", "complaint",
                  "positive-feedback", "upsell", "callback", "supervisor-review", "training"]

# ── Transcript Templates ─────────────────────────────────────────────────────
# 30 realistic conversation templates grouped by issue & quality

TRANSCRIPTS = {
    "Billing Issue": [
        """Agent: Thank you for calling TechCo billing support, my name is {agent}. How can I assist you today?
Customer: Hi {agent}, I noticed a double charge on my last statement for $49.99. I should have only been charged once.
Agent: I completely understand your concern. Let me pull up your account right away… I can see the duplicate charge from March 3rd. That should not have happened.
Customer: Right, it's been there for a week now and I was getting worried.
Agent: I sincerely apologize for the inconvenience. I'm initiating a refund for the duplicate amount right now. You should see the $49.99 credited back within 3-5 business days.
Customer: Oh great, that's a relief. Thank you.
Agent: You're welcome! I've also added a note to your account so this won't happen again. Is there anything else I can help you with?
Customer: No, that's all. Thanks for being so quick about it!
Agent: My pleasure! Thank you for calling TechCo. Have a great day!""",

        """Agent: Good afternoon, TechCo billing department, this is {agent}. What can I help you with?
Customer: Yeah, I got charged $129 for a premium plan but I never upgraded. I'm on the basic plan.
Agent: That sounds frustrating. Let me check your account history… I see an upgrade was processed on the 15th. Were you contacted about a promotional offer?
Customer: Someone called me about a trial but I said I'd think about it. I didn't agree to anything!
Agent: I understand, and I'm sorry this happened. I can see the note here. Let me reverse the upgrade immediately and process a refund for the difference.
Customer: How long will that take?
Agent: The refund will appear in 5-7 business days. I'm also reverting your plan back to Basic right now. I'll send you a confirmation email within the hour.
Customer: Okay, fine. Just make sure it doesn't happen again.
Agent: Absolutely. I've flagged your account to prevent unauthorized changes. Is there anything else?
Customer: No.  Bye.""",

        """Agent: Hello, TechCo billing, {agent} speaking. How may I help you?
Customer: I want to know why my bill jumped from $30 to $55 this month. Nobody told me about any price increases.
Agent: I apologize for the surprise. Let me look into this for you. I can see that a new data add-on was activated on your account on March 2nd.
Customer: I didn't authorize that. This is unacceptable.
Agent: I completely understand your frustration. Let me remove that add-on right now and credit the difference back to your account. Done — you'll see $25 credited on your next statement.
Customer: Fine. But I want an email confirmation.
Agent: Absolutely, I'm sending that to you right now. You should receive it within a few minutes. Is there anything else I can help with?
Customer: No, just fix it properly this time.
Agent: It's taken care of. Thank you for your patience, and again, I apologize for the inconvenience.""",
    ],

    "Technical Problem": [
        """Agent: TechCo technical support, this is {agent}. What seems to be the issue?
Customer: My internet has been dropping every 10 minutes for the past three days. I work from home and this is killing my productivity.
Agent: I'm really sorry to hear that. That must be incredibly frustrating when you're trying to work. Let me run a diagnostic on your connection right now.
Customer: I already restarted the router twice.
Agent: I appreciate you trying that. Looking at your line stats, I can see some packet loss on your connection. It appears there might be an issue with the signal reaching your area. I'm going to push a firmware update to your router remotely that should stabilize things.
Customer: You can do that remotely?
Agent: Yes! I'm pushing it now — your router will restart in about 2 minutes. After it comes back up, the connection should be much more stable. If it persists beyond 24 hours, we'll schedule a technician visit at no charge.
Customer: Okay, I appreciate that. Thank you.
Agent: You're welcome! I'll also follow up with a call tomorrow to make sure everything's working. Is there anything else I can help with?""",

        """Agent: Hey, TechCo tech support, {agent} here. What's going on?
Customer: I can't connect to your app at all. It just shows a spinning wheel and then crashes.
Agent: Let me help you with that. What device are you using?
Customer: iPhone 14, latest iOS.
Agent: Got it. There was a known issue with our last app update on iOS. Can you try force-closing the app and clearing the cache? Go to Settings, then Apps, find TechCo, and tap Clear Cache.
Customer: Okay, let me try… Done. Opening the app now… Oh! It's working! Thank you!
Agent: That was the issue. We pushed a fix in version 4.2.1 — make sure your auto-updates are on to get it. Anything else?
Customer: No, you fixed it. Thanks a lot!""",

        """Agent: TechCo support, {agent} speaking.
Customer: Look, I've called three times this week about my email not syncing. Nobody has fixed it and I'm done being patient.
Agent: I'm sorry you've had to call multiple times — that's not the experience we want for you. Let me look at the previous tickets and make sure we resolve this now.
Customer: You better, because I'm about to cancel my subscription.
Agent: I understand. Looking at your account, I see the previous agents reset your sync settings, but the underlying issue is your mailbox exceeded the 50GB limit. That's what's blocking the sync. I'm upgrading your storage right now — no extra charge — and forcing a full re-sync.
Customer: Why didn't anyone tell me that before?
Agent: I honestly don't know, and I apologize. The re-sync should complete within the hour. I'm also setting up a follow-up notification for myself to check on this tomorrow morning.
Customer: Fine. I'll give it one more chance.
Agent: Thank you for your patience. You'll also receive an email with your new storage details shortly.""",
    ],

    "Account Access": [
        """Agent: Thank you for calling TechCo, this is {agent}. How can I help you today?
Customer: Hi {agent}, I've been trying to access my account for two days now and I keep getting an error saying my password is incorrect. I reset it three times already!
Agent: I'm so sorry to hear that, that must be incredibly frustrating. Let me pull up your account details right away.
Customer: Yes it's very frustrating. I have important files I need to access.
Agent: I completely understand. I can see your account here. It looks like there's a security flag that was triggered due to multiple failed login attempts. I'm going to clear that for you now.
Customer: Oh okay. Will that fix it?
Agent: Yes, it should resolve the issue immediately. I've cleared the flag and I'm sending you a new password reset link now. Please check your email.
Customer: Let me check… Yes I got it! Let me try… It worked! Thank you so much!
Agent: Wonderful! I'm glad that's sorted. Is there anything else I can help with today?
Customer: No, that's all. Thanks for being so helpful!""",

        """Agent: TechCo account services, {agent} speaking. How may I help?
Customer: I got locked out of my account and the two-factor authentication keeps sending codes to my old phone number.
Agent: Oh no, I can see how that would be a problem. For security, I'll need to verify your identity. Can you provide your date of birth and the last four digits of the card on file?
Customer: Sure, it's July 14th 1990, and the card ends in 4823.
Agent: Perfect, verified. I'm now updating your 2FA phone number. What's your current mobile number?
Customer: It's 555-0187.
Agent: Done. I've sent a test code to that number now. Can you confirm the code you received?
Customer: I got 847293.
Agent: That matches. Your two-factor authentication is fully updated. You can now log in normally. Is there anything else?
Customer: No, that's everything. You guys are great. Thank you!""",
    ],

    "Service Outage": [
        """Agent: TechCo support, {agent} here. I understand there may be some service disruption in your area. How can I help?
Customer: Yeah, everything went down about an hour ago. Internet, TV, everything. And I have a Zoom meeting in 30 minutes!
Agent: I sincerely apologize for the disruption. We are aware of a service outage affecting your area due to a fiber cut. Our crews are already on-site working to restore service.
Customer: How long is this going to take?
Agent: Current estimate is approximately 2-3 hours. I know that doesn't help with your meeting in 30 minutes. As a temporary solution, I can activate a mobile hotspot on your account at no charge for the next 24 hours.
Customer: You can do that? That would actually help a lot.
Agent: Yes! I've just activated it. Check your TechCo app — you should see a temporary hotspot option under your services.
Customer: I see it! Connecting now… Okay it works. Not the fastest but good enough for a video call.
Agent: Exactly. And once the main service is restored, you'll be notified automatically. I'll also apply a pro-rated credit to your next bill for the downtime.
Customer: That's fair. Thank you for being helpful about this.""",

        """Agent: TechCo service desk, {agent} speaking.
Customer: My service has been down since last night. This is ridiculous — I pay $80 a month and can't even use the internet.
Agent: I completely understand your frustration, and you're right to be upset. Let me check the status in your area. I can see there was a network issue that has since been resolved, but it looks like your equipment may need a remote reset.
Customer: I've already unplugged and replugged everything.
Agent: I appreciate you trying that. Let me push a remote signal reset — this is different from a power cycle. It resets the connection on our end... Done. Can you check if your lights are showing solid green?
Customer: Give me a second… Yeah, they're all green now. And the internet is back! Finally.
Agent: Excellent! I'm glad it's working. As compensation for the outage, I'm applying a one-day service credit to your account. You'll see it on your next statement.
Customer: That's the least you could do. Thanks anyway.""",
    ],

    "Refund Request": [
        """Agent: TechCo support, {agent} here. How can I help you today?
Customer: I want a full refund. I bought the premium streaming package two weeks ago and half the channels don't work.
Agent: I'm sorry to hear about the issue with your streaming package. That's definitely not what you signed up for. Let me check which channels are affected.
Customer: Sports Max, Movie Central, and Kids Zone — all buffering constantly or just black screens.
Agent: I can see the issue. These channels had a CDN migration last week that affected some accounts. I'm going to reset your streaming authentication, which should fix all three channels immediately.
Customer: But I still want some kind of refund for the two weeks it didn't work properly.
Agent: Absolutely, that's fair. I'm processing a pro-rated refund of $14.50 for the two weeks of degraded service. Would you like that as a credit on your next bill or back to your original payment method?
Customer: Back to my card, please.
Agent: Done. You'll see the $14.50 refund in 3-5 business days. And your streaming channels should all be working now — can you check one for me?
Customer: Let me try Sports Max… It's loading… Yes! It's working perfectly now. Thank you.
Agent: Great! Sorry again for the inconvenience. Enjoy the premium package!""",

        """Agent: Hello, TechCo customer care, {agent} speaking.
Customer: I need to cancel and get my money back. I signed up last month and the service is terrible.
Agent: I'm sorry to hear you've had a bad experience. Before I process that, can you tell me what's been the main issue? I'd like to see if there's something we can fix.
Customer: The internet speed is nothing close to what was promised. I'm paying for 500 Mbps and getting maybe 50.
Agent: That's a huge gap and shouldn't be the case. Let me run a line test… I can see your actual provisioned speed is only set to 50 Mbps. It looks like there was an error during setup. Let me correct that right now.
Customer: So it was your mistake?
Agent: It appears so, yes. I've updated your speed tier to 500 Mbps. It'll take about 10 minutes for the change to fully take effect. I'm also crediting your account for last month since you weren't getting what you paid for.
Customer: Okay, I'll see how the speed is and maybe I'll stay. But if it's still slow I'm leaving.
Agent: That's completely fair. I'll follow up with you in 48 hours to check. Does that work?
Customer: Yeah, fine. Thanks.""",
    ],

    "Product Inquiry": [
        """Agent: TechCo sales support, {agent} here. What can I help you with today?
Customer: Hi, I'm interested in your business fiber plan. Can you walk me through the options?
Agent: Of course! We have three business plans. Our Starter plan at $79/month includes 200 Mbps symmetric speeds, 5 email accounts, and basic cloud storage. The Professional plan at $149/month bumps that to 1 Gbps with 25 email accounts and 1TB cloud storage. And our Enterprise plan at $299/month offers 2.5 Gbps, unlimited email, 5TB cloud, and a dedicated account manager.
Customer: The Professional plan sounds good. Is there a contract?
Agent: We offer month-to-month or annual. The annual plan saves you 15%, bringing Professional down to $127/month.
Customer: That's a good deal. Can I try it first?
Agent: Absolutely! We have a 30-day money-back guarantee on all business plans. If you're not satisfied in the first 30 days, you get a full refund, no questions asked.
Customer: Perfect. Let me talk to my business partner and I'll call back to sign up.
Agent: Sounds great! I'll email you a summary of what we discussed. What's the best email address?""",

        """Agent: TechCo, {agent} speaking. How can I help?
Customer: I want to know the difference between your home security packages.
Agent: Great question! We have two packages. The Essential package at $29.99/month includes 4 cameras, motion sensors, and 24/7 monitoring. The Premium package at $49.99/month adds smart locks, video doorbell, smoke detectors, and priority emergency response.
Customer: Do I need professional installation?
Agent: The Essential package is self-installation with our step-by-step app guide. Premium includes free professional installation. Both come with a 2-year warranty.
Customer: Okay, I think I want the Premium. Can I schedule installation?
Agent: Absolutely! The earliest available slot is this Thursday between 10 AM and 2 PM. Would that work for you?
Customer: Thursday works. Let's do it.
Agent: Wonderful! I've scheduled your installation. You'll receive a confirmation email with all the details. Welcome to TechCo Security!""",
    ],

    "Subscription Change": [
        """Agent: TechCo subscriptions, {agent} here. What can I do for you?
Customer: I want to downgrade my plan from Premium to Basic. I don't use half the features.
Agent: I understand. Before I process that, the Premium plan includes cloud storage and priority support which you've been using regularly. If you downgrade, you'll lose access to those. Is that okay?
Customer: I mainly just use the internet. The other stuff is nice but not worth the extra $40.
Agent: That's fair. I can downgrade you effective at the end of your current billing cycle, which is April 1st. That way you keep Premium benefits until then.
Customer: Sounds good. Go ahead.
Agent: Done! Your plan will switch to Basic on April 1st. Your new monthly rate will be $39.99. I'll send you an email confirming the change.
Customer: Perfect, thank you.
Agent: You're welcome! And if you ever want to upgrade again, we can do that anytime. Have a great day!""",
    ],

    "Data Privacy": [
        """Agent: TechCo privacy department, {agent} speaking. How can I assist you?
Customer: I want to know what data you have on me and I want it deleted under GDPR.
Agent: Absolutely, that's your right. I can help you with both a data access request and a deletion request. For security, I'll need to verify your identity first. Can you provide the email address on your account?
Customer: It's john.smith@email.com.
Agent: Thank you. I'm sending a verification link to that email now. Once you click it, I can proceed with your request. The data access report will be ready within 30 days as required by law, but we typically have it done in about 7 business days.
Customer: What about deletion?
Agent: After you confirm the data access request, we'll process the deletion. Please note that some data like billing records must be retained for tax purposes for 7 years, but all personal usage data, call logs, and browsing history will be permanently deleted.
Customer: That's fine. I just want my personal stuff removed.
Agent: Understood. Once you verify via email, everything will be set in motion. You'll receive updates at each step. Is there anything else?
Customer: No, that covers it. Thanks for being straightforward.""",
    ],

    "General Inquiry": [
        """Agent: TechCo support, {agent} here. How can I help you today?
Customer: Hi, I'm just calling to check my account balance and when my next bill is due.
Agent: Sure! Let me pull that up. Your current balance is $0 — your last payment of $79.99 was processed on March 1st. Your next bill will be generated on March 29th and due by April 15th.
Customer: Great. And can you confirm my plan?
Agent: You're on the Home Premium plan with 500 Mbps internet, cable TV with 200+ channels, and home phone. Your monthly rate is $79.99.
Customer: Perfect. That's all I needed. Thank you!
Agent: Happy to help! Have a wonderful day!""",

        """Agent: Hello, TechCo here, {agent} speaking.
Customer: I'm moving to a new address next month and need to transfer my service. Is that possible?
Agent: Absolutely! We can transfer your existing plan to a new address. When is your move date?
Customer: April 15th.
Agent: Perfect. What's the new address?
Customer: 456 Oak Street, Apartment 12B.
Agent: Let me check availability… Great news, we have full coverage at that address! I've scheduled the transfer for April 15th. A technician will come between 8 AM and 12 PM to set everything up. There's no extra charge for the transfer.
Customer: That's great! Will my plan and price stay the same?
Agent: Exactly the same — no changes at all. I'll send you a confirmation with all the details.
Customer: Awesome. Thank you so much!""",
    ],
}

# ── Summaries for analyses ────────────────────────────────────────────────────
SUMMARIES = {
    "Billing Issue": [
        "Customer reported a duplicate charge on their account. Agent identified and refunded the overcharge promptly. Issue fully resolved.",
        "Customer disputed an unauthorized plan upgrade. Agent reversed the charge and refunded the difference. Flagged account to prevent recurrence.",
        "Customer noticed unexpected increase in their bill. Agent found an unauthorized add-on, removed it, and issued a credit.",
    ],
    "Technical Problem": [
        "Customer experienced intermittent internet drops affecting remote work. Agent ran diagnostics, pushed firmware update, and scheduled follow-up.",
        "Customer's mobile app was crashing on launch. Agent identified known iOS bug and guided through cache clear. Issue resolved immediately.",
        "Recurring email sync issue — third call. Agent discovered mailbox storage limit was the root cause, upgraded storage at no charge, and initiated full re-sync.",
    ],
    "Account Access": [
        "Customer locked out due to security flag triggered by multiple failed login attempts. Agent cleared the flag and sent password reset link. Access restored.",
        "Customer's two-factor authentication linked to old phone number. Agent verified identity and updated 2FA to current number. Issue resolved.",
    ],
    "Service Outage": [
        "Area-wide fiber cut outage. Agent provided temporary mobile hotspot while crews restored service. Applied pro-rated credit for downtime.",
        "Customer reported overnight service loss. Agent performed remote signal reset after power cycle failed. Service restored and one-day credit applied.",
    ],
    "Refund Request": [
        "Customer requested refund for non-working premium streaming channels. Agent reset authentication, fixed channels, and issued partial refund for downtime.",
        "Customer threatened cancellation due to slow speeds. Agent discovered provisioning error, corrected speed tier, and credited full month.",
    ],
    "Product Inquiry": [
        "Customer inquired about business fiber plans. Agent presented all three tiers with pricing. Customer interested in Professional annual plan, requested follow-up email.",
        "Customer asked about home security packages. Agent explained Essential vs Premium options. Customer chose Premium with professional installation scheduled.",
    ],
    "Subscription Change": [
        "Customer requested downgrade from Premium to Basic plan. Agent explained feature impact and scheduled downgrade for end of billing cycle.",
    ],
    "Data Privacy": [
        "Customer submitted GDPR data access and deletion request. Agent verified identity, initiated data export, and scheduled personal data deletion.",
    ],
    "General Inquiry": [
        "Customer called to check account balance and billing date. Agent confirmed details and plan information. Quick and efficient call.",
        "Customer requested service address transfer for upcoming move. Agent verified coverage and scheduled technician visit. No additional charges.",
    ],
}


def weighted_choice(items_with_weights):
    """Pick from [(item, weight), …] based on weights."""
    items, weights = zip(*items_with_weights)
    return random.choices(items, weights=weights, k=1)[0]


def score_for_agent(agent_code):
    """Return a realistic score based on agent tier."""
    tier = AGENT_TIERS.get(agent_code, "mid")
    lo, hi = TIER_SCORE_RANGE[tier]
    return random.randint(lo, hi)


def sentiment_for_score(score):
    if score >= 75:
        return "Positive"
    elif score >= 55:
        return random.choice(["Neutral", "Positive"])
    elif score >= 40:
        return random.choice(["Neutral", "Negative"])
    else:
        return "Negative"


def emotion_for_sentiment(sentiment):
    if sentiment == "Positive":
        return random.choice(["Calm", "Satisfied", "Calm", "Satisfied"])
    elif sentiment == "Neutral":
        return random.choice(["Calm", "Concerned", "Confused", "Calm"])
    else:
        return random.choice(["Frustrated", "Angry", "Impatient", "Disappointed"])


def resolution_for_score(score):
    if score >= 75:
        return "Resolved"
    elif score >= 50:
        return random.choice(["Resolved", "Partially Resolved", "Resolved"])
    else:
        return random.choice(["Partially Resolved", "Not Resolved"])


def score_breakdown(total):
    """Split total score into 5 sub-scores."""
    comm    = min(30, max(5, int(total * 0.30) + random.randint(-3, 3)))
    problem = min(25, max(3, int(total * 0.25) + random.randint(-3, 3)))
    empathy = min(20, max(2, int(total * 0.20) + random.randint(-2, 2)))
    comply  = min(15, max(1, int(total * 0.15) + random.randint(-2, 2)))
    close   = min(10, max(1, int(total * 0.10) + random.randint(-1, 1)))
    return comm, problem, empathy, comply, close


def random_timestamp(weeks_back):
    """Random datetime within the last N weeks."""
    now = datetime.now(timezone.utc)
    delta = timedelta(
        weeks=random.uniform(0, weeks_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return now - delta


def generate_phone():
    return f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"


# ── Main seed function ────────────────────────────────────────────────────────
def seed():
    print("🔧 Creating tables …")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # ── Clean existing demo data ──────────────────────────────────────────────
    existing = db.query(models.Company).filter(models.Company.email == DEMO_EMAIL).first()
    if existing:
        print("🗑  Removing existing demo company …")
        db.delete(existing)
        db.commit()

    # ── 1. Company ────────────────────────────────────────────────────────────
    print("🏢 Creating demo company …")
    company = models.Company(name=DEMO_COMPANY, email=DEMO_EMAIL, plan_type="enterprise")
    db.add(company)
    db.flush()

    # ── 2. User ───────────────────────────────────────────────────────────────
    print("👤 Creating admin user …")
    user = models.User(
        company_id=company.id,
        email=DEMO_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        role="company_owner",
    )
    db.add(user)
    db.flush()

    # ── 3. Agents ─────────────────────────────────────────────────────────────
    print("🧑‍💼 Creating 12 agents …")
    agent_db_map = {}
    for code, name, email, dept, shift in AGENTS:
        agent = models.Agent(
            company_id=company.id,
            agent_code=code,
            name=name,
            email=email,
            department=dept,
            shift=shift,
            is_active=True,
        )
        db.add(agent)
        db.flush()
        agent_db_map[code] = agent

    # ── 4. Calls + Analyses ───────────────────────────────────────────────────
    print(f"📞 Generating {NUM_CALLS} call records …")
    all_calls = []
    for i in range(NUM_CALLS):
        issue = weighted_choice(ISSUES)
        agent_code, agent_name, *_ = random.choice(AGENTS)
        agent_obj = agent_db_map[agent_code]

        score   = score_for_agent(agent_code)
        sent    = sentiment_for_score(score)
        emo     = emotion_for_sentiment(sent)
        res     = resolution_for_score(score)
        prof    = max(1, min(5, score // 20))
        frust   = max(1, min(5, 6 - prof))
        comm, prob, emp, comp, close = score_breakdown(score)

        ts = random_timestamp(WEEKS_OF_DATA)
        duration = round(random.uniform(1.5, 22.0), 1)
        contact_id = f"C-{1001 + i}"
        source  = random.choices(SOURCES, weights=[0.60, 0.25, 0.15], k=1)[0]
        ctype   = random.choices(CALL_TYPES, weights=[0.80, 0.20], k=1)[0]

        # Pick transcript
        issue_transcripts = TRANSCRIPTS.get(issue, TRANSCRIPTS["General Inquiry"])
        transcript = random.choice(issue_transcripts).format(agent=agent_name)

        # Pick summary
        issue_summaries = SUMMARIES.get(issue, SUMMARIES["General Inquiry"])
        summary = random.choice(issue_summaries)

        call = models.Call(
            company_id=company.id,
            contact_id=contact_id,
            agent_id=agent_code,
            agent_name=agent_name,
            agent_ref_id=agent_obj.id,
            conversation=transcript,
            duration=duration,
            source=source,
            call_type=ctype,
            phone_number=generate_phone(),
            status="complete",
            uploaded_at=ts,
        )
        db.add(call)
        db.flush()

        analysis = models.CallAnalysis(
            call_id=call.id,
            company_id=company.id,
            sentiment=sent,
            issue=issue,
            score=score,
            summary=summary,
            emotion=emo,
            resolution_status=res,
            agent_professionalism=prof,
            customer_frustration=frust,
            communication_score=comm,
            problem_solving_score=prob,
            empathy_score=emp,
            compliance_score=comp,
            closing_score=close,
            created_at=ts,
        )
        db.add(analysis)

        # Tags (1-3 random tags per call)
        for tag in random.sample(TAGS_POOL, k=random.randint(1, 3)):
            db.add(models.CallTag(call_id=call.id, tag=tag))

        all_calls.append(call)

        if (i + 1) % 50 == 0:
            print(f"  … {i + 1}/{NUM_CALLS} calls")

    # ── 5. Live Sessions ──────────────────────────────────────────────────────
    print("🔴 Creating live AI agent sessions …")
    statuses = ["active", "analyzing", "complete", "complete", "complete"]
    for j in range(15):
        agent_code, agent_name, *_ = random.choice(AGENTS)
        started = random_timestamp(1)  # last week
        st = random.choice(statuses)
        ended = started + timedelta(minutes=random.randint(3, 20)) if st == "complete" else None
        dur = int((ended - started).total_seconds()) if ended else random.randint(60, 600)

        # Link to a call record if complete
        linked_call = all_calls[random.randint(0, len(all_calls) - 1)] if st == "complete" and j < len(all_calls) else None

        session = models.LiveSession(
            company_id=company.id,
            call_id=linked_call.id if linked_call else None,
            agent_id=agent_code,
            agent_name=agent_name,
            contact_id=f"C-LIVE-{9000 + j}",
            phone_number=generate_phone(),
            status=st,
            started_at=started,
            ended_at=ended,
            duration_sec=dur,
        )
        db.add(session)
        db.flush()

        # Add messages for each session
        num_msgs = random.randint(4, 12)
        speakers = ["agent", "customer"]
        greetings = [
            "Thank you for calling TechCo support. How can I assist you today?",
            "Hello, this is TechCo AI assistant. I'm here to help you.",
            "Welcome to TechCo support. What can I help you with?",
        ]
        customer_openers = [
            "Hi, I'm having an issue with my account.",
            "I need help with my billing statement.",
            "My internet isn't working properly.",
            "I want to change my subscription plan.",
            "I have a question about your service.",
        ]
        agent_responses = [
            "I understand. Let me look into that for you right away.",
            "I'm sorry to hear that. Let me check your account.",
            "Of course! I can help you with that.",
            "Let me pull up your details. One moment please.",
            "I see the issue. Here's what we can do.",
            "I've found the problem. Let me fix that for you now.",
            "Your account has been updated. Is there anything else?",
            "The issue has been resolved. You should see the change within 24 hours.",
        ]
        customer_responses = [
            "Oh, that would be great. Thank you.",
            "How long will that take?",
            "I've been waiting for days for this to be fixed.",
            "Can you also check my last payment?",
            "That's exactly what I needed. Thanks!",
            "I appreciate your help with this.",
            "Perfect, that answers my question.",
        ]

        msg_ts = started
        for seq in range(1, num_msgs + 1):
            if seq == 1:
                speaker = "agent"
                text = random.choice(greetings)
            elif seq == 2:
                speaker = "customer"
                text = random.choice(customer_openers)
            else:
                speaker = speakers[seq % 2]
                text = random.choice(agent_responses if speaker == "agent" else customer_responses)

            msg_ts += timedelta(seconds=random.randint(5, 45))
            db.add(models.LiveMessage(
                session_id=session.id,
                seq=seq,
                speaker=speaker,
                text=text,
                timestamp=msg_ts,
            ))

    # ── 6. Evaluation Framework ───────────────────────────────────────────────
    print("📋 Creating evaluation framework …")
    db.add(models.EvaluationFrameworkModel(
        company_id=company.id,
        config=[
            {
                "id": "communication", "name": "Communication Skills", "weight": 30,
                "criteria": [
                    {"id": "greeting",  "label": "Professional Greeting",     "weight": 10},
                    {"id": "clarity",   "label": "Clear & Concise Language",  "weight": 10},
                    {"id": "tone",      "label": "Positive Tone",            "weight": 10},
                ],
            },
            {
                "id": "problem_solving", "name": "Problem Solving", "weight": 25,
                "criteria": [
                    {"id": "diagnosis",  "label": "Issue Identified Quickly",  "weight": 10},
                    {"id": "resolution", "label": "First Call Resolution",     "weight": 15},
                ],
            },
            {
                "id": "empathy", "name": "Empathy & Rapport", "weight": 20,
                "criteria": [
                    {"id": "acknowledge", "label": "Acknowledges Frustration",  "weight": 10},
                    {"id": "personalise", "label": "Personalises Interaction",  "weight": 10},
                ],
            },
            {
                "id": "compliance", "name": "Compliance & Process", "weight": 15,
                "criteria": [
                    {"id": "verify", "label": "Identity Verification",  "weight": 7},
                    {"id": "data",   "label": "Data Privacy Adherence", "weight": 8},
                ],
            },
            {
                "id": "close", "name": "Call Closing", "weight": 10,
                "criteria": [
                    {"id": "summary",      "label": "Summarises Resolution",  "weight": 5},
                    {"id": "satisfaction", "label": "Asks for Satisfaction",  "weight": 5},
                ],
            },
        ],
    ))

    # ── 7. Audit Log entries ──────────────────────────────────────────────────
    print("📝 Creating audit log …")
    actions = [
        ("login",          "Admin logged in"),
        ("upload_calls",   "Uploaded 50 calls from batch_march.csv"),
        ("upload_calls",   "Uploaded 25 calls from weekly_report.json"),
        ("analyze",        "Single transcript analysis"),
        ("export_report",  "Exported PDF report"),
        ("update_framework","Updated evaluation framework weights"),
        ("login",          "Admin logged in"),
        ("upload_calls",   "Uploaded 30 calls from ai_agent_logs.csv"),
    ]
    for action, detail in actions:
        db.add(models.AuditLog(
            company_id=company.id,
            user_id=user.id,
            action=action,
            detail=detail,
            created_at=random_timestamp(4),
        ))

    # ── Commit everything ─────────────────────────────────────────────────────
    db.commit()
    db.close()

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║               ✅  SEED DATA COMPLETE                        ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Company : {DEMO_COMPANY:<42}    ║
║  Login   : {DEMO_EMAIL:<42}    ║
║  Password: {DEMO_PASSWORD:<42}    ║
║                                                              ║
║  Created:                                                    ║
║    • 1 company (enterprise plan)                             ║
║    • 1 admin user                                            ║
║    • 12 agents across 3 departments                          ║
║    • {NUM_CALLS} call records with full AI analysis              ║
║    • 15 live AI agent sessions with messages                 ║
║    • 1 evaluation framework                                  ║
║    • 8 audit log entries                                     ║
║                                                              ║
║  Data spans {WEEKS_OF_DATA} weeks for realistic trend charts.         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    seed()
