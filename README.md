# Peptide Research Vault

A static, searchable peptide research database for CrossFit Blaze (Naples, FL). Evidence-ranked compounds with 311 citations across 6 categories.

## Features

- **46 unique compounds** with evidence tier rankings (S through F)
- **311 research citations** from PubMed, ClinicalTrials.gov, FDA, and peer-reviewed journals
- Search and filter by tier
- Detail drawer for each compound
- Tabbed reference browser by category (RCTs, Preclinical, Reviews, Official, Observational, Adverse)
- Mobile-first responsive design
- No build step — pure static HTML/CSS/JS

## Deployment

Drop the entire folder onto any static host:

```bash
# GitHub Pages
git push origin main
# then enable Pages in repo Settings > Pages > Source: main / root

# Any static server
npx serve .
```

The site uses relative paths (`./data/peptide_details.json`) so it works at any subpath without configuration.

## Project Structure

```
index.html              — Main page
styles.css              — All styles (dark theme, responsive)
app.js                  — Data fetching, rendering, search, filters, drawer
data/
  peptide_details.json  — Source data (78 entries, 311 references)
  source-summary.md     — Data provenance notes
```

## Evidence Tier System

| Tier | Meaning |
|------|---------|
| S | FDA-approved or Phase 3 RCT |
| A | Strong preclinical + limited human data |
| B | Promising early-phase or combo data |
| C | Mixed evidence or niche application |
| D | Minimal or outdated evidence |
| F | High risk / no quality human data |

## Disclaimer

This site is for **educational and informational purposes only**. It does not provide medical advice, diagnosis, or treatment recommendations. Consult a licensed physician before making any health decisions.

## Data Sources

- PubMed / NIH
- ClinicalTrials.gov
- FDA DailyMed
- Peer-reviewed journals
