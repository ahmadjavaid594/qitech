-- qitech.user_type_cat_assigns definition

CREATE TABLE `user_type_cat_assigns` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_type_id` bigint unsigned NOT NULL,
  `user_type_category_id` bigint unsigned NOT NULL,
  `head_office_id` bigint unsigned NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=65 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;