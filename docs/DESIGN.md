# Design

The single source for look and feel. Status: approved to build as a draft. The owner corrects things as we go; every correction is made here first, then in the code.

All values below become CSS variables in one file: reimbursement_council/web/static/tokens.css. Pages use only these variables. To restyle the whole app, change that file and this doc together.

## Direction
Calm and clear, like a good bank receipt, not like a hospital ad. The member should feel "I know exactly what is happening with my money." The reviewer should feel "everything I need is on one screen." Lots of white space, strong numbers, very little decoration. Color is used only to mean something (lane, confidence), never for decoration.

Not this: purple gradients, glassy cards, stock photos of doctors, a hero with three feature cards, emoji icons.

We are not imitating Bupa's brand. Our own name, our own colors.

## References
- https://www.ahmedalluqmani.com (owner's pick): minimal. Take the restraint: lots of space, few colors, type doing the work. The page renders with JavaScript, so its styles could not be read from here.
  First UI task: open it with Playwright, take desktop and phone screenshots, read its computed fonts, colors and spacing, and update the tokens in this doc to match its feel. Keep our lane colors and the Arabic font. Show the owner the before and after, then build.

Other kinds of screens worth looking at:
- A banking app's transaction detail screen (how money and status are shown)
- A tax or receipt scanner app's review screen (how read fields are confirmed)
- A support or moderation tool's queue card (how a reviewer sees evidence and acts fast)

## Fonts
- IBM Plex Sans Arabic for Arabic text, IBM Plex Sans for Latin text. They are designed as a pair, so mixed Arabic and English receipts look consistent.
- IBM Plex Mono for amounts, IDs and codes, so numbers line up.
- Sizes: 14, 16, 20, 24, 32. Body 16. Amounts on result screens 32.

## Color tokens
| Token | Use | Value |
|---|---|---|
| --ink | Main text | #14211F |
| --ink-muted | Secondary text | #5B6866 |
| --paper | Page background | #F7F6F2 |
| --surface | Cards | #FFFFFF |
| --line | Borders and dividers | #E3E1DA |
| --accent | Primary buttons, links | #0F5C55 |
| --lane-approve | Auto approve, paid | #1E7A46 |
| --lane-selffix | Member can fix | #2D5FA8 |
| --lane-review | Human review | #B7791F |
| --lane-reject | Rejected | #B4322B |
| --confidence-low | Highlight for low confidence fields | #FCE9B2 |

CHECK: contrast of every text and background pair passes WCAG AA. Fix the value here if not.

## Spacing and shape
- Spacing scale (px): 4, 8, 12, 16, 24, 32, 48.
- Radius: 8 for cards and inputs, 999 for status pills. Nothing else.
- One shadow level only, for cards on the paper background.

## Direction of text
- Every screen works in Arabic (right to left) and English (left to right). Use logical CSS properties (margin-inline-start, not margin-left).
- Amounts and dates show in the member's chosen language. Original receipt text is always shown as printed.

## Components (build once, reuse everywhere)
- StatusPill: lane label with its lane color.
- AmountBlock: large amount, currency, one line of why under it.
- FieldRow: label, value, source tag (QR, read, confirmed), confidence highlight, edit action.
- DocumentViewer: image with boxes over the fields we read, linked to FieldRow on hover or tap.
- VoteRow: council member name, score bar from 0 to 1, weight, one line reason.
- RequestCard: the self-fix ask, with two buttons: "Add it now" and "Send to a reviewer (slower)".
- ReviewActions: approve, approve a different amount, reject with reason, ask the member.
- MetricTile and the ablation table for the metrics page.

## Screens
1. Member upload. Pick patient, add photos.
2. Member preview. FieldRows, low confidence highlighted, AmountBlock with estimated payout, warnings before submit.
3. Member result. StatusPill, AmountBlock or RequestCard or reason.
4. Reviewer card. DocumentViewer on one side; on the other: lane reason, VoteRows, hard rule results, payout math, ReviewActions.
5. Metrics. MetricTiles, reliability diagram, ablation table.

Sketch of the reviewer card:
```
+------------------------------+---------------------------------+
| [receipt image]              | Why it is here:                 |
|  [box] Al Noor Clinic        |  Council disagrees (spread 0.31)|
|  [box] 2026-11-20            |                                 |
|  [box] Total 340.00 SAR      | Document checker  0.92  ======  |
|                              | Coverage checker  0.88  =====   |
|                              | Price checker     0.41  ==      |
|                              |   "Consult fee is 2x network"   |
|                              | Case reviewer     0.80  =====   |
|                              | History           0.50  ===     |
|                              |                                 |
|                              | Payout: 300.00 SAR (network cap)|
|                              | [Approve] [Other amount]        |
|                              | [Reject]  [Ask member]          |
+------------------------------+---------------------------------+
```

## Checks before any UI is called done
- Playwright screenshots: desktop and phone, Arabic and English, for every screen.
- Check against this doc. Run an Impeccable audit. Fix and re-shoot.
