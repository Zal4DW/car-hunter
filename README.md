# Car Hunter

**Your personal used-car buyer's assistant, powered by Claude.**

Car Hunter is a plugin for [Claude Cowork](https://claude.ai) that does the boring, time-consuming parts of shopping for a used car in the UK - searching every major listing site, tracking prices over time, spotting the deals hiding in plain sight, and turning the whole mess into a clear picture of what's actually worth buying.

You don't need to know how to code. You just chat with Claude.

## What it does for you

- **Searches every major UK car site at once.** AutoTrader, Cazoo, Cinch, CarWow, Motorpoint, manufacturer approved-used programmes, and big dealer groups - all checked in a single run.
- **Filters to exactly the car you want.** Variant, age, mileage, budget, distance from home, must-have options - set your preferences once, reuse them forever.
- **Remembers what it's seen.** Every search gets saved. Next time, Car Hunter tells you which cars are new, which have sold, and which dealers have dropped the price.
- **Tells you which cars are good value.** Not just "cheapest" - it works out what each car *should* cost given its age, mileage, trim and options, then flags the ones priced below that as genuine deals.
- **Builds a beautiful interactive dashboard.** Depreciation curves, a negotiation radar to spot stale listings ripe for a cheeky offer, a spec-premium chart showing what each extra actually adds to the price, and a sortable table of every car on the market right now.
- **Works for any car.** Audi e-tron GT, BMW M4, Tesla Model 3, Porsche Taycan, Volvo V60 - whatever you're hunting, tell Claude once and it learns the specifics.

## Getting started

### 1. Install the plugin

In Claude Cowork, add Car Hunter from the plugin marketplace (or point it at this repository if you're installing manually).

### 2. Install Claude in Chrome

Car Hunter reads car listings using the **Claude in Chrome** browser extension. Most car sites actively block automated scrapers, so Car Hunter drives a real Chrome window instead - one you've signed in with, just like you would normally. Install it from [Anthropic's Claude in Chrome page](https://www.anthropic.com/news/claude-for-chrome) and sign in before you run your first search.

You'll need a Chrome window open when Car Hunter is working.

### 3. Tell Claude which car you want

Open Claude Cowork and type:

```
/setup-car
```

Claude will walk you through a friendly conversation - what make and model, what trim levels you're interested in, what your budget and maximum mileage are, how far you're willing to travel, which options matter to you (panoramic roof? premium audio? massage seats?), and which ones you'd consider deal-breakers.

This only takes a few minutes, and it's a one-time setup. Claude saves everything as your **car profile**.

### 4. Go hunting

```
/search-cars
```

Claude opens Chrome, works through every site you've configured, deduplicates cars that appear on multiple platforms, and comes back with a detailed report: every matching car, sorted cheapest-first, grouped by trim level, with direct clickable links to each listing. You'll see price, year, mileage, colour, where the dealer is, how far away they are, how long the car has been advertised, and which of your must-have options each one has.

Run it again tomorrow, next week, or next month - Claude compares against previous searches and highlights what's changed.

### 5. See the big picture

```
/build-dashboard
```

Claude builds an interactive HTML dashboard from your searches and opens it in your browser. You'll get:

- **Depreciation curves** showing how each trim level loses value with age, with an automatic marker at the point where the losses flatten out (the sweet spot for buying).
- **Deal scores** ranking every current listing from "genuine bargain" (green) to "overpriced" (red), based on what the car *should* cost given its age, mileage, and options.
- **Spec premium analysis** revealing what each optional extra actually adds to the market price - so you know whether that £3,000 premium audio upgrade is really worth £3,000 on the used market.
- **Negotiation radar** plotting every car by "how long has it been listed" versus "how overpriced is it", so you can spot stale listings where the dealer will likely accept an offer.
- **Market pulse** telling you how many cars are active, how many have sold since last time, how many are new arrivals, and the average days on market.
- **Full sortable table** of every car, filterable by variant, generation, mileage, budget, and value rating.

## What you'll need

- **Claude Cowork** subscription
- **Claude in Chrome** extension, installed and signed in
- A few minutes to answer Claude's setup questions about the car you want
- Patience to let Claude work through the sites (a full search across every platform takes a few minutes)

You do **not** need any coding experience, Python, command-line tools, or developer setup. If you can chat with Claude, you can use Car Hunter.

## Tips for getting the most out of it

- **Run searches regularly.** The real power comes from tracking changes over time. Weekly or fortnightly is ideal.
- **Be honest about your must-haves.** The fewer truly essential options you mark, the more cars you'll see. Be strict about the things you really care about and flexible about the rest.
- **Trust the value score, but verify in person.** Car Hunter is brilliant at finding cars that look like good deals on paper. It cannot check service history, smell the interior, or hear the suspension creaking. Always inspect before you buy.
- **Use the negotiation radar before making an offer.** Cars that have been sitting on a forecourt for 60+ days are much more negotiable than last week's arrivals.
- **Update your profile as your search evolves.** Learned that you actually *do* care about the cold-weather pack? Run `/setup-car` again and add it.

## Something not working?

- **Claude says it can't reach the car sites.** Check that Chrome is open and that the Claude in Chrome extension is active and signed in.
- **Claude can't find your profile.** Run `/setup-car` to create one. You need at least one profile before you can search.
- **The dashboard looks empty.** Run `/search-cars` at least once first - the dashboard is built from your search history.
- **You want to track a second car.** Just run `/setup-car` again. Car Hunter supports multiple profiles and will ask which one you mean.

## Licence and honest disclaimers

Car Hunter is released under the [Creative Commons Attribution-NonCommercial 4.0 International Licence (CC BY-NC 4.0)](LICENSE). You're welcome to use it, share it, and adapt it for personal and non-commercial use - just give credit. Commercial use, including reselling the plugin or running it on behalf of a dealership or broker, is not permitted.

**Please read this bit.** Car Hunter is a research and shortlisting tool, not financial or purchase advice. Its "value scores" and "expected prices" are statistical estimates based on the data it has seen - they don't know whether a specific car has been in an accident, been poorly maintained, or has a dodgy gearbox. Always inspect any car in person (or pay for a professional inspection), verify the service history, and satisfy yourself before parting with any money.

Car Hunter reads publicly listed data from third-party websites. It is not affiliated with, endorsed by, or sponsored by AutoTrader, Cazoo, Cinch, CarWow, Motorpoint, or any dealer group. Please respect each site's terms of service when using it.

See [LICENSE](LICENSE) for the full terms.

---

Built with care by [Paul Bratcher](https://www.linkedin.com/in/paul-bratcher/) - pay it forward. If Car Hunter helps you find your next car, tell someone else about it.
