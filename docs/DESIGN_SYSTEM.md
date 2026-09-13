# Design system

The visual direction uses deep navy navigation, muted cool-grey surfaces, teal primary actions and restrained semantic status colours. Business content leads: the dashboard starts with current liabilities and review work, while the invoice page puts the original beside its record.

Tokens and shared styles live in `frontend/src/style.css`; common components live in `ui.tsx`. Do not create a separate visual theme for a new module.

| Element | Convention |
|---|---|
| Typography | DM Sans for interface text; Manrope for headings; system-font fallback |
| Core palette | Navy `#102c3a`, teal `#087e80`, page background `#f5f7fa`, borders `#e4e9ef` |
| Heading hierarchy | One page H1, section H2s, compact subgroup H3s |
| Spacing | Main content 24–34px; panels 20–24px; controls and compact rows use smaller consistent gaps |
| Corners | Panels 12px, form controls/actions 7px, badges 5px |
| Buttons | Solid teal for the primary action, bordered neutral for secondary actions, icons with accessible names |
| Status | Green for verified/paid/active; amber for review/possible missing; red for failed/overdue/rejected; neutral for drafts |
| Forms | Persistent labels, required indicators, browser validation plus backend validation, fieldsets disabled during locked states |
| Tables | Clear header row, aligned currency, server-side search/filtering and pagination; horizontal scrolling within the table on small screens |
| Dialogs | Native modal dialog, trapped browser focus, escape to close, explicit confirmation for financial/destructive decisions |
| Feedback | Loading indicator, empty-state explanation/action, inline errors and temporary success notifications |
| Motion | Minimal transitions, reduced-motion support |

The sidebar collapses behind a mobile navigation control. The invoice comparison stacks on smaller screens. Tables remain readable through contained horizontal scrolling rather than shrinking text to fit. PDF rendering loads only when an invoice's original is opened. Password fields, document content and financial actions are functional components rather than decorative placeholders.

New pages should reuse `PageHead`, `Badge`, `Form`, `Modal`, `SearchBox`, `Pager`, `Loading`, `ErrorBox` and `Empty`. Keep important labels visible, give icon-only actions accessible names, and verify keyboard use, narrow viewports and long business names. The initial interface was visually reviewed at desktop and 390px mobile widths; a formal accessibility audit has not been performed.
