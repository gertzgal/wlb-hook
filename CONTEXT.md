# wlb-hook domain glossary

- **Workday**: the span from a person's first Claude Code CLI prompt of the local calendar day to now. Breaks count. Resets at midnight.
- **Budget**: the maximum Workday length the person intends, in hours. Default 9.
- **Overwork**: the state where the Workday exceeds the Budget.
- **Gate**: the moment a prompt is intercepted because of Overwork and the person must make a Choice.
- **Choice**: one of *Stop*, *One last prompt*, *Workaholic*.
  - **Stop**: this prompt is dropped and every further prompt today is blocked without a Gate. Done for the day.
  - **One last prompt**: this prompt runs; the next prompt gates again. A one-shot allowance.
  - **Workaholic**: the rest of the Workday is unlocked. Requires an Excuse.
- **Day state**: *open* (no Choice yet), *stopped* (a Stop was chosen), *unlocked* (Workaholic was chosen).
- **Excuse**: the person's justification for choosing Workaholic. Mandatory.
- **Event log**: the append-only record of every Gate and Choice, one line per event, shared by the hook and any future dashboard.
- **Demo override**: fabricated Workday inputs used to trigger a Gate on demand.
