# Audela SQL Cookbook

Based on the Audela module presentation deck, this cookbook turns the platform topics into practical SQL patterns you can reuse in day-to-day work. It is organized by module: Portal BI, Finance, Credit, IFRS 9, ETL, and Project.

The examples are written for a multi-tenant Audela deployment and assume you always scope queries by `tenant_id` and, when relevant, `company_id`.

## How to use this cookbook

1. Start from the business question, not the table name.
2. Filter by tenant first, then narrow by company, module, status, or date.
3. Prefer CTEs for readable analytics queries.
4. Store reusable logic as saved questions or reports when the SQL becomes stable.
5. When a query feeds a dashboard, keep the grain explicit and stable.

## Common conventions

- `tenant_id` isolates each customer or workspace.
- `company_id` usually isolates a finance entity within a tenant.
- Date windows are written as `:date_from` and `:date_to` placeholders.
- Status filters are written as lowercase strings, matching the platform conventions.
- Examples use PostgreSQL-friendly SQL.

## Quick table map

- BI portal: `data_sources`, `collections`, `questions`, `dashboards`, `dashboard_cards`, `query_runs`, `audit_events`, `reports`, `report_blocks`, `file_folders`, `file_assets`
- Finance: `finance_companies`, `finance_accounts`, `finance_transactions`, `finance_report_snapshots`, `finance_categories`, `finance_category_rules`, `finance_bank_connections`, `finance_bank_account_links`, `finance_gl_accounts`, `finance_ledger_vouchers`, `finance_ledger_lines`, `finance_accounting_periods`, `finance_liabilities`
- Credit: `credit_countries`, `credit_sectors`, `credit_ratings`, `credit_facility_types`, `credit_collateral_types`, `credit_guarantee_types`, `credit_borrowers`, `credit_deals`, `credit_facilities`, `credit_covenants`, `credit_facility_utilizations`, `credit_collaterals`, `credit_guarantors`
- ETL: `etl_connections`
- Project: `project_workspaces`

## 1. Portal BI recipes

### 1.1 List the active data sources for a tenant

Use this when you want to confirm which sources are available for analysis.

```sql
select
  ds.id,
  ds.name,
  ds.type,
  ds.base_url,
  ds.created_at
from data_sources ds
where ds.tenant_id = :tenant_id
order by ds.created_at desc, ds.name;
```

### 1.2 Find the most used saved questions

This helps identify the queries that matter most to users.

```sql
select
  q.id,
  q.name,
  count(qr.id) as run_count,
  max(qr.started_at) as last_run_at
from questions q
left join query_runs qr
  on qr.question_id = q.id
 and qr.tenant_id = q.tenant_id
where q.tenant_id = :tenant_id
group by q.id, q.name
order by run_count desc, last_run_at desc nulls last;
```

### 1.3 Build a dashboard coverage view

This shows which questions are already wired into dashboards.

```sql
select
  d.id as dashboard_id,
  d.name as dashboard_name,
  count(dc.id) as card_count,
  count(distinct dc.question_id) as question_count
from dashboards d
left join dashboard_cards dc
  on dc.dashboard_id = d.id
 and dc.tenant_id = d.tenant_id
where d.tenant_id = :tenant_id
group by d.id, d.name
order by dashboard_name;
```

### 1.4 Inspect failed query runs

Use this to debug broken analytics content.

```sql
select
  qr.id,
  qr.question_id,
  q.name as question_name,
  qr.started_at,
  qr.duration_ms,
  qr.error
from query_runs qr
left join questions q
  on q.id = qr.question_id
where qr.tenant_id = :tenant_id
  and qr.status = 'error'
order by qr.started_at desc;
```

### 1.5 Create a lightweight audit trail

This pattern is useful when you want to understand who changed what.

```sql
select
  ae.id,
  ae.user_id,
  ae.event_type,
  ae.created_at,
  ae.payload_json
from audit_events ae
where ae.tenant_id = :tenant_id
order by ae.created_at desc
limit 100;
```

## 2. Finance recipes

### 2.1 Show the cash position by company and account

This is the basic treasury view.

```sql
select
  fc.id as company_id,
  fc.name as company_name,
  fa.id as account_id,
  fa.name as account_name,
  fa.currency,
  fa.balance,
  fa.limit_amount
from finance_accounts fa
join finance_companies fc
  on fc.id = fa.company_id
 and fc.tenant_id = fa.tenant_id
where fa.tenant_id = :tenant_id
order by fc.name, fa.name;
```

### 2.2 Calculate net cash movement for a period

Positive values are inflows; negative values are outflows.

```sql
select
  ft.company_id,
  fc.name as company_name,
  sum(ft.amount) as net_movement,
  sum(case when ft.amount > 0 then ft.amount else 0 end) as inflows,
  sum(case when ft.amount < 0 then -ft.amount else 0 end) as outflows
from finance_transactions ft
join finance_companies fc
  on fc.id = ft.company_id
 and fc.tenant_id = ft.tenant_id
where ft.tenant_id = :tenant_id
  and ft.txn_date between :date_from and :date_to
group by ft.company_id, fc.name
order by fc.name;
```

### 2.3 Spot overdue accounting periods

Use this to see which books remain open.

```sql
select
  ap.company_id,
  fc.name as company_name,
  ap.period_start,
  ap.period_end,
  ap.is_closed,
  ap.closed_at,
  ap.note
from finance_accounting_periods ap
join finance_companies fc
  on fc.id = ap.company_id
 and fc.tenant_id = ap.tenant_id
where ap.tenant_id = :tenant_id
  and ap.is_closed = false
order by ap.period_end desc;
```

### 2.4 Review liabilities by maturity

This is a practical debt and liquidity view.

```sql
select
  fl.company_id,
  fc.name as company_name,
  fl.name,
  fl.principal_amount,
  fl.outstanding_amount,
  fl.interest_rate,
  fl.maturity_date,
  fl.next_payment_date
from finance_liabilities fl
join finance_companies fc
  on fc.id = fl.company_id
 and fc.tenant_id = fl.tenant_id
where fl.tenant_id = :tenant_id
order by fl.maturity_date nulls last, fl.name;
```

### 2.5 Reconcile ledger activity

This compares transactional activity to journal entries.

```sql
select
  fv.voucher_date,
  fv.reference,
  fv.description,
  count(fl.id) as line_count,
  sum(fl.debit) as total_debit,
  sum(fl.credit) as total_credit
from finance_ledger_vouchers fv
join finance_ledger_lines fl
  on fl.voucher_id = fv.id
 and fl.tenant_id = fv.tenant_id
where fv.tenant_id = :tenant_id
  and fv.voucher_date between :date_from and :date_to
group by fv.voucher_date, fv.reference, fv.description
order by fv.voucher_date desc, fv.reference;
```

## 3. Credit recipes

### 3.1 Build a portfolio summary by borrower

This is the entry point for credit monitoring.

```sql
select
  cb.id as borrower_id,
  cb.name as borrower_name,
  count(distinct cd.id) as deal_count,
  count(distinct cf.id) as facility_count,
  sum(cf.approved_amount) as total_approved_amount
from credit_borrowers cb
left join credit_deals cd
  on cd.borrower_id = cb.id
 and cd.tenant_id = cb.tenant_id
left join credit_facilities cf
  on cf.deal_id = cd.id
 and cf.tenant_id = cd.tenant_id
where cb.tenant_id = :tenant_id
group by cb.id, cb.name
order by total_approved_amount desc nulls last, borrower_name;
```

### 3.2 Identify deals still in review

Use this for pipeline management and escalation.

```sql
select
  cd.id,
  cd.code,
  cb.name as borrower_name,
  cd.purpose,
  cd.requested_amount,
  cd.currency,
  cd.status,
  cd.created_at
from credit_deals cd
join credit_borrowers cb
  on cb.id = cd.borrower_id
 and cb.tenant_id = cd.tenant_id
where cd.tenant_id = :tenant_id
  and cd.status in ('in_review', 'pending', 'draft')
order by cd.created_at desc;
```

### 3.3 Track facility utilization against approvals

This answers the simple question: how much of the approved limit is already drawn?

```sql
select
  cf.id as facility_id,
  cd.code as deal_code,
  cb.name as borrower_name,
  cf.approved_amount,
  coalesce(sum(cfu.amount), 0) as utilized_amount,
  case
    when cf.approved_amount = 0 then null
    else round(coalesce(sum(cfu.amount), 0) / cf.approved_amount * 100, 2)
  end as utilization_pct
from credit_facilities cf
join credit_deals cd
  on cd.id = cf.deal_id
 and cd.tenant_id = cf.tenant_id
join credit_borrowers cb
  on cb.id = cd.borrower_id
 and cb.tenant_id = cd.tenant_id
left join credit_facility_utilizations cfu
  on cfu.facility_id = cf.id
 and cfu.tenant_id = cf.tenant_id
where cf.tenant_id = :tenant_id
group by cf.id, cd.code, cb.name, cf.approved_amount
order by utilization_pct desc nulls last;
```

### 3.4 Find covenants approaching due date

This is a standard risk-control query.

```sql
select
  cc.id,
  cb.name as borrower_name,
  cd.code as deal_code,
  cc.name as covenant_name,
  cc.metric,
  cc.operator,
  cc.threshold_value,
  cc.frequency,
  cc.due_date,
  cc.status
from credit_covenants cc
join credit_borrowers cb
  on cb.id = cc.borrower_id
 and cb.tenant_id = cc.tenant_id
left join credit_deals cd
  on cd.id = cc.deal_id
 and cd.tenant_id = cc.tenant_id
where cc.tenant_id = :tenant_id
  and cc.status = 'active'
  and cc.due_date is not null
  and cc.due_date <= current_date + interval '30 days'
order by cc.due_date, cb.name;
```

### 3.5 Summarize collateral coverage

This gives a quick collateral-to-exposure view.

```sql
select
  cb.name as borrower_name,
  sum(coalesce(cco.market_value, 0)) as collateral_market_value,
  sum(coalesce(cco.market_value, 0) * (1 - coalesce(cco.haircut_pct, 0) / 100.0)) as haircutted_value
from credit_borrowers cb
left join credit_collaterals cco
  on cco.borrower_id = cb.id
 and cco.tenant_id = cb.tenant_id
where cb.tenant_id = :tenant_id
group by cb.name
order by haircutted_value desc nulls last;
```

## 4. IFRS 9 recipes

The PDF describes IFRS 9 as a governance and expected-credit-loss module. In practice, you usually build it from the same credit portfolio data and then layer stage, scenario, and ECL fields on top.

### 4.1 Segment exposures by stage

If your staging is stored outside the credit core tables, start from the borrower or facility grain and add the staging fields from your model.

```sql
select
  cb.name as borrower_name,
  cd.code as deal_code,
  cf.approved_amount,
  coalesce(cfd.stage, 'unknown') as ifrs_stage,
  count(*) as exposure_count
from credit_borrowers cb
join credit_deals cd
  on cd.borrower_id = cb.id
 and cd.tenant_id = cb.tenant_id
join credit_facilities cf
  on cf.deal_id = cd.id
 and cf.tenant_id = cd.tenant_id
left join lateral (
  select null::text as stage
) cfd on true
where cb.tenant_id = :tenant_id
group by cb.name, cd.code, cf.approved_amount, cfd.stage
order by cb.name, cd.code;
```

### 4.2 Build a stress scenario comparison

This pattern compares a base case and a stressed case using stored scenario outputs.

```sql
with scenario_values as (
  select
    s.scenario_name,
    s.borrower_name,
    s.ecl_amount
  from ifrs9_scenario_results s
  where s.tenant_id = :tenant_id
    and s.scenario_name in ('base', 'stress')
)
select
  borrower_name,
  max(case when scenario_name = 'base' then ecl_amount end) as base_ecl,
  max(case when scenario_name = 'stress' then ecl_amount end) as stress_ecl,
  max(case when scenario_name = 'stress' then ecl_amount end)
  - max(case when scenario_name = 'base' then ecl_amount end) as delta_ecl
from scenario_values
group by borrower_name
order by delta_ecl desc nulls last;
```

### 4.3 Summarize model governance artifacts

This is useful for control teams and model committees.

```sql
select
  m.model_name,
  m.version,
  m.status,
  m.last_reviewed_at,
  m.owner
from ifrs9_models m
where m.tenant_id = :tenant_id
order by m.last_reviewed_at desc nulls last, m.model_name;
```

### 4.4 Track ECL snapshots over time

Use this when you need trend analysis and auditability.

```sql
select
  s.as_of_date,
  s.portfolio_name,
  s.total_exposure,
  s.total_ecl,
  s.stage_1_exposure,
  s.stage_2_exposure,
  s.stage_3_exposure
from ifrs9_ecl_snapshots s
where s.tenant_id = :tenant_id
order by s.as_of_date desc;
```

## 5. ETL recipes

### 5.1 List configured connections

```sql
select
  ec.id,
  ec.name,
  ec.type,
  ec.created_at
from etl_connections ec
where ec.tenant_id = :tenant_id or ec.tenant_id is null
order by ec.created_at desc, ec.name;
```

### 5.2 Find the latest run for each pipeline

If your ETL execution log is stored separately, this is the pattern to follow: one row per pipeline, latest status first.

```sql
with latest_runs as (
  select
    r.pipeline_name,
    r.status,
    r.started_at,
    r.finished_at,
    row_number() over (
      partition by r.pipeline_name
      order by r.started_at desc
    ) as rn
  from etl_runs r
  where r.tenant_id = :tenant_id
)
select
  pipeline_name,
  status,
  started_at,
  finished_at
from latest_runs
where rn = 1
order by pipeline_name;
```

### 5.3 Detect stale sources

This is the standard freshness check.

```sql
select
  s.source_name,
  s.last_success_at,
  s.row_count,
  s.error_message
from etl_source_status s
where s.tenant_id = :tenant_id
  and (s.last_success_at is null or s.last_success_at < current_timestamp - interval '24 hours')
order by s.last_success_at nulls first, s.source_name;
```

## 6. Project recipes

### 6.1 Inspect the current project workspace state

```sql
select
  pw.tenant_id,
  pw.updated_by_user_id,
  pw.state_json,
  pw.updated_at
from project_workspaces pw
where pw.tenant_id = :tenant_id;
```

### 6.2 Track items by status in a project board

If your project state JSON stores cards, columns, or tasks, flatten it with JSON operators in the database or in the application layer.

```sql
select
  pw.tenant_id,
  pw.updated_at,
  pw.state_json -> 'board' as board_state
from project_workspaces pw
where pw.tenant_id = :tenant_id;
```

## Reusable patterns

### Pattern A: tenant-safe join

Always join both the foreign key and the tenant scope when the table is tenant-aware.

```sql
select *
from a
join b
  on b.id = a.b_id
 and b.tenant_id = a.tenant_id;
```

### Pattern B: latest row per entity

```sql
with ranked as (
  select
    t.*,
    row_number() over (
      partition by t.entity_id
      order by t.created_at desc
    ) as rn
  from some_table t
  where t.tenant_id = :tenant_id
)
select *
from ranked
where rn = 1;
```

### Pattern C: dashboard-ready aggregate

```sql
select
  date_trunc('month', t.txn_date) as month,
  sum(t.amount) as amount
from finance_transactions t
where t.tenant_id = :tenant_id
group by 1
order by 1;
```

### Pattern D: risk ranking

```sql
select
  borrower_name,
  risk_score,
  case
    when risk_score >= 80 then 'high'
    when risk_score >= 50 then 'medium'
    else 'low'
  end as risk_band
from borrower_risk_view
where tenant_id = :tenant_id
order by risk_score desc;
```

## Suggested starting projects

1. Build one finance cash dashboard from `finance_transactions` and `finance_accounts`.
2. Build one credit watchlist from `credit_borrowers`, `credit_deals`, and `credit_covenants`.
3. Build one BI operations dashboard from `query_runs`, `dashboards`, and `audit_events`.
4. Add one ETL freshness panel and one project workspace summary panel.

## Notes

- Some IFRS 9 examples refer to modeled outputs that may live in custom tables or views in your deployment.
- If you materialize snapshots, keep the snapshot grain consistent so trends stay comparable.
- If you want this cookbook to become a training asset, each recipe can be converted into an exercise plus sample dataset.
