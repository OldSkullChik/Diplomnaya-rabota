# OMSU API chart catalog contract - 2026-06-17

The OMSU API now exposes dashboard analytics in two layers:

1. Legacy desktop-compatible chart keys:
   - `area.charts.score_trend`
   - `area.charts.topic_distribution`
   - `area.charts.sentiment_balance`
   - `area.charts.appeal_types`
   - `area.charts.negative_probability`
   - `area.charts.comment_volume`
   - `area.charts.responsible_parties`
   - `area.charts.quality_mix`
   - plus additional flat series such as `authority_aspects`, `impact_classes`, `decision_mix`, `confidence_bands`, `source_contribution`, `negative_topics`, `score_buckets`, `relevance_filter`.

   These keys intentionally remain simple label/value arrays so the existing PyQt desktop client can keep rendering them as line/bar cards.

2. Typed cross-client catalog:
   - `area.charts.chart_catalog`
   - `area.charts.chart_layout`

Each `chart_catalog` item has:

```json
{
  "id": "topic_distribution",
  "title": "Темы ЖКХ",
  "type": "bar",
  "meaning": "What management question this chart answers.",
  "weight": 88,
  "priority": 5,
  "unit": "count",
  "data": [{"label": "waste_cleaning", "value": 4}],
  "client_hints": {"desktop": "main", "android": "summary"}
}
```

The `type` field is the intended rendering hint for Android and the newer desktop UI:

- `line`
- `bar`
- `horizontal_bar`
- `donut`
- `pie`
- `stacked_bar`
- `gauge`
- `delta`
- `funnel`
- `histogram`
- `heatmap`
- `ratio`

The `weight` field is semantic importance, not a numeric value for plotting. Higher-weight charts answer more important management questions and should be shown earlier on constrained screens.

The `priority` field is display order. Clients should sort by `priority` unless a local layout overrides it.

The `meaning` field is intended for tooltips, help screens, report generation and diploma-facing explanations. It makes sure every chart has a defensible purpose rather than existing only as visual filler.

## Desktop and Android Layout

`GET /api/v1/omsu/snapshot/` includes:

```json
{
  "widgets": {
    "main": ["score_trend", "topic_distribution", "sentiment_balance", "appeal_types"],
    "spare": ["negative_probability", "comment_volume", "responsible_parties", "quality_mix"],
    "desktop": {
      "primary": ["score_trend", "topic_distribution", "sentiment_balance", "appeal_types"],
      "drawer": ["negative_probability", "comment_volume", "responsible_parties"]
    },
    "android": {
      "summary": ["score_trend", "negative_probability", "sentiment_balance", "topic_distribution"],
      "details": ["appeal_types", "responsible_parties", "authority_aspects"]
    }
  }
}
```

Existing desktop code may continue using `main` and `spare`. Android should prefer `widgets.android.summary` for the first screen and `widgets.android.details` for expanded analytics.

## Current Chart Set

The current server-generated catalog includes:

- `score_trend` - line chart for previous/current OMSU score.
- `score_delta` - delta card for score movement.
- `negative_probability` - gauge for negative OMSU probability.
- `relevance_filter` - funnel from analyzed stream to ЖКХ-relevant records.
- `topic_distribution` - bar chart of ЖКХ topics.
- `negative_topics` - horizontal bar chart of topics that drive negative tone.
- `sentiment_balance` - donut chart of negative/neutral/positive tone.
- `appeal_types` - bar chart of complaints, questions, requests and other appeal types.
- `responsible_parties` - bar chart of actors associated with problems.
- `authority_aspects` - bar chart of governance aspects such as supervision or communication.
- `decision_mix` - pie chart of OMSU decision classes.
- `impact_classes` - stacked bar for impact severity.
- `confidence_bands` - model confidence distribution.
- `quality_mix` - data-quality distribution.
- `source_contribution` - source/group contribution to relevant signals.
- `comment_volume` - line/funnel-like volume comparison.
- `item_types` - posts vs comments.
- `score_buckets` - histogram of score severity.
- `topic_sentiment_heatmap` - heatmap of topic by sentiment.
- `coverage_ratio` - percentage of analyzed stream that is ЖКХ-relevant.

This gives both clients enough useful charts without requiring each client to invent its own calculations.
