-- qitech.head_office_organisation_groups definition

CREATE TABLE `head_office_organisation_groups` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `head_office_id` int unsigned NOT NULL,
  `parent_id` bigint unsigned DEFAULT NULL,
  `group` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `head_office_organisation_groups_parent_id_foreign` (`parent_id`),
  KEY `head_office_organisation_groups_head_office_id_foreign` (`head_office_id`),
  CONSTRAINT `head_office_organisation_groups_head_office_id_foreign` FOREIGN KEY (`head_office_id`) REFERENCES `head_offices` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `head_office_organisation_groups_parent_id_foreign` FOREIGN KEY (`parent_id`) REFERENCES `head_office_organisation_groups` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=353 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;