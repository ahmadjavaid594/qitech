-- qitech.be_spoke_form_action_conditions definition

CREATE TABLE `be_spoke_form_action_conditions` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `question_id` bigint unsigned NOT NULL,
  `condition_if_value` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `condition_value` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `condition_value_2` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `condition_action_type` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  `condition_action_value` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `condition_action_value_1` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- qitech.be_spoke_form_categories definition

CREATE TABLE `be_spoke_form_categories` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `reference_type` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `reference_id` int NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  `color` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT '#000',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=120 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- qitech.be_spoke_form_question_groups definition

CREATE TABLE `be_spoke_form_question_groups` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `group_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `stage_id` bigint unsigned NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- qitech.be_spoke_form_record_data definition

CREATE TABLE `be_spoke_form_record_data` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `record_id` bigint unsigned NOT NULL,
  `question_id` bigint unsigned NOT NULL,
  `question_value` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=80 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- qitech.be_spoke_form_stages definition

CREATE TABLE `be_spoke_form_stages` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `stage_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `form_id` bigint unsigned NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- qitech.be_spoke_form_record_data_radact definition

CREATE TABLE `be_spoke_form_record_data_radact` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `data_id` bigint unsigned NOT NULL,
  `is_radact` tinyint NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `be_spoke_form_record_data_radact_data_id_foreign` (`data_id`),
  CONSTRAINT `be_spoke_form_record_data_radact_data_id_foreign` FOREIGN KEY (`data_id`) REFERENCES `be_spoke_form_record_data` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- qitech.be_spoke_form definition

CREATE TABLE `be_spoke_form` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `display_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fields_updated_at` timestamp NULL DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  `add_to_case_manager` tinyint(1) DEFAULT NULL,
  `hide_in_company_timeline` tinyint(1) NOT NULL DEFAULT '0',
  `case_description_field` int DEFAULT NULL,
  `reference_type` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `reference_id` int NOT NULL,
  `is_external_link` tinyint NOT NULL DEFAULT '0',
  `external_link` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `be_spoke_form_category_id` bigint unsigned DEFAULT NULL,
  `is_case_close_priority` tinyint(1) NOT NULL DEFAULT '0',
  `case_close_priority_rule` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `case_close_priority_value` int DEFAULT NULL,
  `case_close_priority_comment` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `requires_final_approval` tinyint NOT NULL DEFAULT '0',
  `note` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `color_code` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_allow_non_approved_emails` tinyint NOT NULL DEFAULT '0',
  `is_archived` tinyint NOT NULL DEFAULT '0',
  `is_deleted` tinyint NOT NULL DEFAULT '0',
  `deleted_at` timestamp NULL DEFAULT NULL,
  `purpose` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `allow_editing_state` enum('disable','minutes','hour','day','week','always') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'always',
  `allow_editing_time` int DEFAULT NULL,
  `allow_responder_update` tinyint(1) NOT NULL DEFAULT '0',
  `limits` int DEFAULT '0',
  `active_limit_by_amount` tinyint(1) NOT NULL DEFAULT '1',
  `amount_total_max_res` tinyint(1) NOT NULL DEFAULT '1',
  `limit_to_one_user` tinyint(1) NOT NULL DEFAULT '1',
  `limit_to_one_location` tinyint(1) NOT NULL DEFAULT '0',
  `limit_by_period_max_state` enum('off','day','month','year') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'month',
  `limit_by_period_max_value` int NOT NULL DEFAULT '1',
  `limit_by_period_min_state` enum('off','day','month','year') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'month',
  `limit_by_period_min_value` int NOT NULL DEFAULT '1',
  `active_limit_by_period` tinyint(1) NOT NULL DEFAULT '1',
  `expiry_state` enum('never_expire','expiry_time') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `expiry_time` datetime DEFAULT NULL,
  `schedule_state` enum('optional','day','date') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'day',
  `schedule_by_day` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  `allow_drafts_off_site` tinyint(1) NOT NULL DEFAULT '0',
  `show_submission_loc` tinyint(1) NOT NULL DEFAULT '1',
  `form_json` json NOT NULL,
  `submitable_to_nhs_lfpse` tinyint(1) NOT NULL DEFAULT '0',
  `limit_by_per_user_value` int NOT NULL DEFAULT '1',
  `limit_by_per_location_value` int NOT NULL DEFAULT '1',
  `case_must_review` tinyint(1) NOT NULL DEFAULT '0',
  `org_groups` json DEFAULT NULL,
  `is_quick_report` tinyint(1) NOT NULL DEFAULT '0',
  `is_qr_code` tinyint(1) NOT NULL DEFAULT '0',
  `created_by_id` bigint unsigned DEFAULT NULL,
  `updated_by_id` bigint unsigned DEFAULT NULL,
  `allow_update_time` int DEFAULT NULL,
  `deleted` tinyint NOT NULL DEFAULT '0',
  `soft_deleted` tinyint(1) NOT NULL DEFAULT '0',
  `submission_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `show_to_responder` tinyint(1) NOT NULL DEFAULT '0',
  `is_draft` tinyint(1) NOT NULL DEFAULT '0',
  `allow_update_state` enum('disable','open','minutes','hour','day','week','always','limit') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'always',
  `generate_qr_code` tinyint(1) NOT NULL DEFAULT '0',
  `allow_delete_submission` int DEFAULT NULL,
  `delete_submission_time` int DEFAULT NULL,
  `allow_delete_select` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `allow_user_to_share_case_log` int NOT NULL DEFAULT '0',
  `form_label` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'common',
  `delete_time_mode` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_allow_case_handler_feedback` tinyint(1) NOT NULL DEFAULT '1',
  `is_close_case_mandatory` tinyint(1) NOT NULL DEFAULT '1',
  `allow_print_by_site_team` tinyint(1) NOT NULL DEFAULT '0',
  `allow_print_by_company_user` tinyint(1) NOT NULL DEFAULT '0',
  `show_in_site_timeline_site` tinyint(1) NOT NULL DEFAULT '1',
  `show_in_site_timeline_company` tinyint(1) NOT NULL DEFAULT '1',
  `show_in_contact_timeline_company` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  KEY `be_spoke_form_be_spoke_form_category_id_foreign` (`be_spoke_form_category_id`),
  KEY `be_spoke_form_created_by_id_foreign` (`created_by_id`),
  KEY `be_spoke_form_updated_by_id_foreign` (`updated_by_id`),
  CONSTRAINT `be_spoke_form_be_spoke_form_category_id_foreign` FOREIGN KEY (`be_spoke_form_category_id`) REFERENCES `be_spoke_form_categories` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `be_spoke_form_created_by_id_foreign` FOREIGN KEY (`created_by_id`) REFERENCES `head_office_users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `be_spoke_form_updated_by_id_foreign` FOREIGN KEY (`updated_by_id`) REFERENCES `head_office_users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `be_spoke_form_chk_1` CHECK (json_valid(`schedule_by_day`))
) ENGINE=InnoDB AUTO_INCREMENT=319 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- qitech.be_spoke_form_lfpse_submissions definition

CREATE TABLE `be_spoke_form_lfpse_submissions` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `be_spoke_form_records_id` bigint unsigned DEFAULT NULL,
  `lfpse_id` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `version` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `outcome_type` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `remarks` varchar(190) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  `reference_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `be_spoke_form_lfpse_submissions_be_spoke_form_records_id_index` (`be_spoke_form_records_id`),
  CONSTRAINT `be_spoke_form_lfpse_submissions_be_spoke_form_records_id_foreign` FOREIGN KEY (`be_spoke_form_records_id`) REFERENCES `be_spoke_form_records` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2505 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- qitech.be_spoke_form_record_drafts definition

CREATE TABLE `be_spoke_form_record_drafts` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL,
  `location_id` int unsigned DEFAULT NULL,
  `form_id` bigint unsigned NOT NULL,
  `json_submission` json DEFAULT NULL,
  `last_used` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  `triggered_record_id` bigint unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `be_spoke_form_record_drafts_user_id_foreign` (`user_id`),
  KEY `be_spoke_form_record_drafts_location_id_foreign` (`location_id`),
  KEY `be_spoke_form_record_drafts_form_id_foreign` (`form_id`),
  KEY `be_spoke_form_record_drafts_triggered_record_id_foreign` (`triggered_record_id`),
  CONSTRAINT `be_spoke_form_record_drafts_form_id_foreign` FOREIGN KEY (`form_id`) REFERENCES `be_spoke_form` (`id`) ON DELETE CASCADE,
  CONSTRAINT `be_spoke_form_record_drafts_location_id_foreign` FOREIGN KEY (`location_id`) REFERENCES `locations` (`id`) ON DELETE CASCADE,
  CONSTRAINT `be_spoke_form_record_drafts_triggered_record_id_foreign` FOREIGN KEY (`triggered_record_id`) REFERENCES `be_spoke_form_records` (`id`),
  CONSTRAINT `be_spoke_form_record_drafts_user_id_foreign` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1422 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- qitech.be_spoke_form_record_update_documents definition

CREATE TABLE `be_spoke_form_record_update_documents` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `be_spoke_form_record_update_id` bigint unsigned NOT NULL,
  `document_id` bigint unsigned NOT NULL,
  `type` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `bsfrud_bsfru` (`be_spoke_form_record_update_id`),
  KEY `be_spoke_form_record_update_documents_document_id_foreign` (`document_id`),
  CONSTRAINT `be_spoke_form_record_update_documents_document_id_foreign` FOREIGN KEY (`document_id`) REFERENCES `documents` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `bsfrud_bsfru` FOREIGN KEY (`be_spoke_form_record_update_id`) REFERENCES `be_spoke_form_record_updates` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=170 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- qitech.be_spoke_form_record_updates definition

CREATE TABLE `be_spoke_form_record_updates` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `be_spoke_form_record_id` bigint unsigned NOT NULL,
  `update` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  `user_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `be_spoke_form_record_updates_be_spoke_form_record_id_index` (`be_spoke_form_record_id`),
  KEY `be_spoke_form_record_updates_user_id_index` (`user_id`),
  CONSTRAINT `be_spoke_form_record_updates_be_spoke_form_record_id_foreign` FOREIGN KEY (`be_spoke_form_record_id`) REFERENCES `be_spoke_form_records` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `be_spoke_form_record_updates_user_id_foreign` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=296 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- qitech.be_spoke_form_records definition

CREATE TABLE `be_spoke_form_records` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `form_id` bigint unsigned NOT NULL,
  `location_id` bigint unsigned NOT NULL,
  `reported_location_id` int unsigned DEFAULT NULL,
  `user_id` bigint unsigned DEFAULT NULL,
  `priority` int NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  `status` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `case_status` tinyint NOT NULL DEFAULT '0',
  `hide` tinyint(1) DEFAULT '0',
  `json_submission` json DEFAULT NULL,
  `raw_form` json DEFAULT NULL,
  `record_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `linked_forms` json DEFAULT NULL,
  `hide_in_company_timeline` tinyint(1) NOT NULL DEFAULT '0',
  `deleted_at` timestamp NULL DEFAULT NULL,
  `is_deleted` int NOT NULL DEFAULT '0',
  `is_qr` tinyint(1) NOT NULL DEFAULT '0',
  `is_show_reported_site` tinyint(1) NOT NULL DEFAULT '1',
  `display_submission` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'both_sites',
  `count_submission` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'both_sites',
  `count_submission_external` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'yes',
  `case_summary` json DEFAULT NULL,
  `location_summary` json DEFAULT NULL,
  `form_involved_sites` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `be_spoke_form_records_reported_location_id_foreign` (`reported_location_id`),
  KEY `be_spoke_form_records_form_id_index` (`form_id`),
  KEY `be_spoke_form_records_location_id_index` (`location_id`),
  KEY `be_spoke_form_records_record_id_index` (`record_id`),
  CONSTRAINT `be_spoke_form_records_reported_location_id_foreign` FOREIGN KEY (`reported_location_id`) REFERENCES `locations` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=108607 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;