---
name: negotiation-coach
description: >
  This skill should be used when the user asks for help negotiating a used
  car purchase: "help me negotiate", "what should I offer", "is this price
  fair", "how do I haggle with the dealer", "draft an offer email", "the
  dealer said X, what do I say", "should I take this deal", or any request
  about the buying/offer/haggling stage for a car they found via car-hunter.
  Builds a data-backed negotiation strategy from the tracked market data:
  evidence pack, offer anchors, scripts, and counters to dealer tactics.
---

# Negotiation Coach

Help the user negotiate a specific car purchase, grounded in the market data car-hunter has collected. The numbers come from the bundled brief script; this skill turns them into a strategy, concrete scripts, and live coaching as the negotiation unfolds.

## Prerequisites

- A car profile and at least one search snapshot (`{profile_name}-searches/` with dated CSVs). Without data, still coach - but say clearly the advice is general, not evidence-based, and offer to run /search-cars first.
- The target listing's `listing_id`. If the user describes the car instead ("the blue RS in Leeds for £62k"), match it against the latest CSV by variant, price, and location, and confirm the match before proceeding.

## Step 1: Build the evidence pack

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/negotiation_brief.py" \
  --profile "${CLAUDE_PLUGIN_DATA}/profiles/{profile_name}.json" \
  --dir "{profile_name}-searches" \
  --listing {listing_id}
```

The JSON brief contains: the target's market position (asking vs modelled price), days on market, price-change history across snapshots, ranked negotiation levers with strengths, suggested offer anchors (opening / target / walk-away), and the closest comparables with price gaps. If the listing is missing from the latest snapshot, it may have sold - tell the user and offer to re-run the search.

## Step 2: Present the assessment

Lead with the verdict, then the evidence:

1. **Is the price fair?** Asking vs modelled market price, in plain terms ("£2,400 over the odds" / "already priced £1,100 under market - this one is about speed, not haggling").
2. **The levers, strongest first** - relay each lever from the brief with its number attached. Evidence beats adjectives: "it has sat for 64 days" lands harder than "it seems stale".
3. **The anchors**: opening offer, realistic target, walk-away. Explain the basis. Remind the user the model cannot see condition, service history, or tyres - an inspection can move every number.
4. **The comparables**: the two or three closest, with price gaps and links - this is the user's printable evidence.

## Step 3: Coach the negotiation

Tailor to where the user is in the process:

**Before contact** - advise on channel (email/phone gives a paper trail and removes showroom pressure), timing (month-end and quarter-end help; a car already reduced and 60+ days in stock helps more), and viewing strategy (view and test drive before talking numbers; note defects calmly - each is a quantifiable deduction).

**Making the offer** - draft the message for them on request. Structure: genuine interest, specific evidence (days listed, comparables, market position), one clear number, polite willingness to walk. Offer the total "out-the-door" price including fees, not a monthly payment.

**Handling dealer responses** - prepare counters for the standard moves:
- *"Another buyer is coming this afternoon"* - fine; the offer stands if that falls through.
- *"The price is already reduced"* - acknowledge, cite the comparables and days listed; the market disagrees.
- *"Best I can do"* on price - pivot to non-price value: tank of charge/fuel, mats, new MOT, fresh service, tyre replacement, extended warranty, delivery.
- *Admin/doc fees appearing late* - re-anchor on out-the-door total; the agreed number includes everything.
- *Monthly-payment framing* - always pull back to total price; finance is a separate negotiation (and dealers earn commission on it - being open to their finance can win a price concession; check early-settlement terms before using that card).
- *Part-exchange muddying the water* - negotiate the car's price first, the PX value second, never as one blended number.

**Closing** - get the agreed spec, price, and included extras in writing before paying a deposit; confirm the deposit is refundable pending inspection/HPI check; for distance sales note the 14-day return rights; never feel bad about walking - the supply lever exists because there genuinely are other cars.

## Step 4: Stay in the loop

Offer to: draft the next reply when the dealer responds, re-assess if the dealer counters with a number ("is £61,250 now a good deal?" - compare against the anchors), and re-run the brief after the next search to see if the car dropped again or sold.

## Important Notes

- Be honest when the user has little leverage (fresh listing, priced under market, scarce variant) - the right play there is speed and decisiveness, not hardball that loses the car.
- All prices in GBP; UK consumer context (Consumer Rights Act 2015 for dealer sales, distance-selling rules). Do not present legal points as legal advice.
- The model's numbers are estimates from listing data. Condition, history, and ownership count - always recommend an inspection and HPI check before money moves.
- Use UK English throughout.
