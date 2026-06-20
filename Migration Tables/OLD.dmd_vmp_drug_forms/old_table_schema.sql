-- qitech.dmd_vmp_drug_forms definition

CREATE TABLE `dmd_vmp_drug_forms` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `vpid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `form_cd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `dmd_vmp_drug_forms_vpid_foreign` (`vpid`),
  KEY `dmd_vmp_drug_forms_form_cd_foreign` (`form_cd`),
  CONSTRAINT `dmd_vmp_drug_forms_form_cd_foreign` FOREIGN KEY (`form_cd`) REFERENCES `dmd_drug_forms` (`cd`) ON DELETE CASCADE,
  CONSTRAINT `dmd_vmp_drug_forms_vpid_foreign` FOREIGN KEY (`vpid`) REFERENCES `dmd_vmps` (`vpid`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=20828 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;