# BUSINESS_COLUMN_NAMING.md — {{project_name}} Controlled Vocabulary

> **PURPOSE:** Defines the semantic meaning of all columns in the `{{project_name}}` project. When encountering raw source column names, translate them into the official business terms below. Every column across every domain MUST use identical naming for identical concepts.

---

## HOW TO USE THIS FILE

1. **Staging models:** Look up raw source column name in "Source Aliases". Replace with "Official Name".
2. **New models:** Use ONLY official names. If a concept is not listed, add it before using it.
3. **Reviewing models:** Flag any column name that does not match this glossary.

---

## ENTITY IDENTIFIERS

| Official Name       | Data Type   | Description                                      | Source Aliases                                     |
|---------------------|-------------|--------------------------------------------------|----------------------------------------------------|
| `account_id`        | text        | Unique identifier for a business account         | `acct_id`, `sf_account_id`, `crm_account_id`  |
| `account_sk`        | text (md5)  | Surrogate key for account dimension              | --                                                 |
| `user_id`           | text        | Unique identifier for a system user              | `uid`, `usr_id`, `member_id`                       |
| `user_sk`           | text (md5)  | Surrogate key for user dimension                 | --                                                 |
| `organization_id`   | text        | Unique identifier for an organization            | `org_id`, `company_id`                             |
| `organization_sk`   | text (md5)  | Surrogate key for organization dimension         | --                                                 |
| `document_id`       | text        | Unique identifier for a document                 | `doc_id`                                           |
| `document_sk`       | text (md5)  | Surrogate key for document dimension             | --                                                 |
| `crunch_id`         | text        | Unique identifier for a crunch                   | `analysis_id`                                      |
| `crunch_sk`         | text (md5)  | Surrogate key for crunch fact                    | --                                                 |
| `checklist_id`      | text        | Unique identifier for a checklist                | `spec_id`                                          |
| `checklist_sk`      | text (md5)  | Surrogate key for checklist dimension            | --                                                 |
| `meeting_id`        | text        | Unique identifier for a meeting                  | `call_id`, `conversation_id`                       |
| `meeting_sk`        | text (md5)  | Surrogate key for meeting fact                   | --                                                 |
| `deal_id`           | text        | Unique identifier for a deal/opportunity         | `opportunity_id`, `opp_id`                         |
| `deal_sk`           | text (md5)  | Surrogate key for deal fact                      | --                                                 |
| `contact_id`        | text        | Unique identifier for a contact                  | `lead_id`, `person_id`                             |
| `contact_sk`        | text (md5)  | Surrogate key for contact dimension              | --                                                 |

---

## FINANCIAL METRICS

| Official Name          | Data Type   | Description                                      | Source Aliases                                     |
|------------------------|-------------|--------------------------------------------------|----------------------------------------------------|
| `revenue`              | numeric     | Gross revenue before deductions                  | `sales`, `gross_sales`, `total_sales`, `amount`    |
| `net_revenue`          | numeric     | Revenue after refunds and discounts              | `net_sales`, `adjusted_revenue`                    |
| `discount_amount`      | numeric     | Total discount applied                           | `discount`, `promo_amount`, `coupon_value`         |
| `refund_amount`        | numeric     | Total refund issued                              | `refund`, `return_amount`, `credit_amount`         |
| `cost`                 | numeric     | Cost of goods/services                           | `cogs`, `cost_of_goods`, `unit_cost`, `expense`    |
| `profit`               | numeric     | Revenue minus cost                               | `margin`, `gross_profit`, `net_profit`             |
| `mrr`                  | numeric     | Monthly recurring revenue                        | `monthly_revenue`, `subscription_revenue`          |
| `arr`                  | numeric     | Annual recurring revenue                         | `annual_revenue`, `yearly_revenue`                 |
| `ltv`                  | numeric     | Customer lifetime value                          | `lifetime_value`, `clv`, `customer_value`          |

---

## USER / CONTACT ATTRIBUTES

| Official Name           | Data Type   | Description                                    | Source Aliases                                     |
|-------------------------|-------------|------------------------------------------------|----------------------------------------------------|
| `contact_name`          | text        | Full name of the contact                       | `name`, `full_name`, `client_name`, `lead_name`    |
| `email`                 | text        | Primary email address                          | `email_address`, `e_mail`, `contact_email`         |
| `phone`                 | text        | Primary phone number                           | `phone_number`, `tel`, `mobile`, `contact_phone`   |
| `customer_segment`      | text        | Business segmentation category                 | `segment`, `tier`, `classification`, `group`       |
| `customer_status`       | text        | Current lifecycle status                       | `status`, `account_status`, `state`                |
| `acquisition_channel`   | text        | How the customer was acquired                  | `source`, `channel`, `referral_source`, `utm_source`|
| `industry`              | text        | Customer's industry vertical                   | `vertical`, `sector`, `business_type`              |
| `company_size`          | text        | Size classification of the company             | `employee_range`, `headcount_band`, `size`         |

---

## DC-SPECIFIC ATTRIBUTES

| Official Name           | Data Type   | Description                                    | Source Aliases                                     |
|-------------------------|-------------|------------------------------------------------|----------------------------------------------------|
| `organization_name`     | text        | Name of the organization                       | `org_name`, `company_name`                         |
| `document_type`         | text        | Classification of document                     | `doc_type`, `file_type`                            |
| `crunch_status`         | text        | Status of a crunch analysis                    | `analysis_status`                                  |
| `checklist_name`        | text        | Name of a checklist/specification              | `spec_name`                                        |

---

## TIMESTAMPS AND DATES

| Official Name       | Data Type    | Description                                      | Source Aliases                                     |
|---------------------|--------------|--------------------------------------------------|----------------------------------------------------|
| `created_at`        | timestamp    | When the record was first created                | `create_date`, `date_created`, `creation_time`     |
| `updated_at`        | timestamp    | When the record was last modified                | `modified_at`, `last_modified`, `update_time`      |
| `deleted_at`        | timestamp    | When the record was soft-deleted                 | `removed_at`, `archived_at`                        |
| `inserted_at`       | timestamp    | When the record was loaded into the warehouse    | `_loaded_at`, `_etl_loaded_at`, `load_time`        |
| `occurred_at`       | timestamp    | When the event/action actually happened          | `event_time`, `action_time`, `timestamp`           |
| `start_date`        | date         | Start of a period or contract                    | `begin_date`, `effective_date`                     |
| `end_date`          | date         | End of a period or contract                      | `expiry_date`, `termination_date`                  |

---

## BOOLEAN FLAGS

| Official Name         | Data Type | Description                                      | Source Aliases                                     |
|-----------------------|-----------|--------------------------------------------------|----------------------------------------------------|
| `is_active`           | boolean   | Whether the entity is currently active           | `active`, `status = 'active'`, `enabled`           |
| `is_deleted`          | boolean   | Whether the entity has been soft-deleted         | `deleted`, `removed`, `archived`                   |
| `is_test`             | boolean   | Whether this is a test/sandbox record            | `test`, `sandbox`, `is_sandbox`                    |
| `has_subscription`    | boolean   | Whether the customer has an active subscription  | `subscribed`, `is_subscriber`                      |
| `is_churned`          | boolean   | Whether the customer has churned                 | `churned`, `lost`, `inactive`                      |

---

## DOCUMENT INTELLIGENCE METRICS

| Official Name            | Data Type | Description                                      | Source Aliases                                     |
|--------------------------|-----------|--------------------------------------------------|----------------------------------------------------|
| `document_count`         | integer   | Number of documents                              | `doc_count`, `num_documents`                       |
| `page_count`             | integer   | Number of pages processed                        | `num_pages`                                        |
| `crunch_count`           | integer   | Number of crunches run                           | `analysis_count`                                   |
| `checklist_item_count`   | integer   | Number of checklist items                        | `spec_item_count`                                  |
| `extraction_count`       | integer   | Number of data extractions                       | `num_extractions`                                  |

---

## ADDING NEW TERMS

When you encounter a raw source column NOT in this glossary:

1. Determine the correct official name following `STYLE_GUIDE.md` conventions.
2. Add it to the appropriate section above.
3. Include the raw source alias for future mapping reference.
4. Use the official name in your model -- NEVER use the raw source alias.
