/*
 Navicat Premium Dump SQL

 Source Server         : localhost-pg
 Source Server Type    : PostgreSQL
 Source Server Version : 170009 (170009)
 Source Host           : localhost:5432
 Source Catalog        : digitalSystem
 Source Schema         : public

 Target Server Type    : PostgreSQL
 Target Server Version : 170009 (170009)
 File Encoding         : 65001

 Date: 08/07/2026 10:58:21
*/


-- ----------------------------
-- Sequence structure for archive_stamp_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."archive_stamp_id_seq";
CREATE SEQUENCE "public"."archive_stamp_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for define_template_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."define_template_id_seq";
CREATE SEQUENCE "public"."define_template_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for director_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."director_id_seq";
CREATE SEQUENCE "public"."director_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for operation_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."operation_id_seq";
CREATE SEQUENCE "public"."operation_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for register_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."register_id_seq";
CREATE SEQUENCE "public"."register_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for register_question_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."register_question_id_seq";
CREATE SEQUENCE "public"."register_question_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for roles_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."roles_id_seq";
CREATE SEQUENCE "public"."roles_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for scan_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."scan_id_seq";
CREATE SEQUENCE "public"."scan_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for scan_images_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."scan_images_id_seq";
CREATE SEQUENCE "public"."scan_images_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for task_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."task_id_seq";
CREATE SEQUENCE "public"."task_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for task_mark_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."task_mark_id_seq";
CREATE SEQUENCE "public"."task_mark_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for task_progress_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."task_progress_id_seq";
CREATE SEQUENCE "public"."task_progress_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for users_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."users_id_seq";
CREATE SEQUENCE "public"."users_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for workflows_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."workflows_id_seq";
CREATE SEQUENCE "public"."workflows_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Table structure for archive_stamp
-- ----------------------------
DROP TABLE IF EXISTS "public"."archive_stamp";
CREATE TABLE "public"."archive_stamp" (
  "id" int4 NOT NULL DEFAULT nextval('archive_stamp_id_seq'::regclass),
  "template_name" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "template_format" int4 NOT NULL,
  "show_field_labels" int4,
  "fields_json" text COLLATE "pg_catalog"."default" NOT NULL,
  "create_time" timestamp(6),
  "update_time" timestamp(6),
  "operator" varchar(30) COLLATE "pg_catalog"."default" NOT NULL
)
;
COMMENT ON COLUMN "public"."archive_stamp"."id" IS 'ID';
COMMENT ON COLUMN "public"."archive_stamp"."template_name" IS '模版名称';
COMMENT ON COLUMN "public"."archive_stamp"."template_format" IS '章格式; 0: 6格章; 1: 8格章';
COMMENT ON COLUMN "public"."archive_stamp"."show_field_labels" IS '是否显示字段; 默认:显示; 0: 不显示';
COMMENT ON COLUMN "public"."archive_stamp"."fields_json" IS '归档章字段';
COMMENT ON COLUMN "public"."archive_stamp"."create_time" IS '创建时间';
COMMENT ON COLUMN "public"."archive_stamp"."update_time" IS '更新时间';
COMMENT ON COLUMN "public"."archive_stamp"."operator" IS '创建者';

-- ----------------------------
-- Records of archive_stamp
-- ----------------------------

-- ----------------------------
-- Table structure for define_template
-- ----------------------------
DROP TABLE IF EXISTS "public"."define_template";
CREATE TABLE "public"."define_template" (
  "id" int4 NOT NULL DEFAULT nextval('define_template_id_seq'::regclass),
  "template_name" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "field_info" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "creator" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "create_date" timestamp(6)
)
;
COMMENT ON COLUMN "public"."define_template"."id" IS 'ID';
COMMENT ON COLUMN "public"."define_template"."template_name" IS '模板名称';
COMMENT ON COLUMN "public"."define_template"."field_info" IS '字段信息（包含坐标）JSON 格式';
COMMENT ON COLUMN "public"."define_template"."creator" IS '创建者';
COMMENT ON COLUMN "public"."define_template"."create_date" IS '创建日期';

-- ----------------------------
-- Records of define_template
-- ----------------------------

-- ----------------------------
-- Table structure for director
-- ----------------------------
DROP TABLE IF EXISTS "public"."director";
CREATE TABLE "public"."director" (
  "id" int4 NOT NULL DEFAULT nextval('director_id_seq'::regclass),
  "register_id" int4,
  "archive_type" varchar(25) COLLATE "pg_catalog"."default" NOT NULL,
  "category" varchar(25) COLLATE "pg_catalog"."default" NOT NULL,
  "doc_number" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "director_info" text COLLATE "pg_catalog"."default" NOT NULL,
  "source" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "create_date" timestamp(6) NOT NULL,
  "update_date" timestamp(6) NOT NULL,
  "operator" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "title" varchar(100) COLLATE "pg_catalog"."default"
)
;
COMMENT ON COLUMN "public"."director"."id" IS 'ID';
COMMENT ON COLUMN "public"."director"."register_id" IS '登记ID';
COMMENT ON COLUMN "public"."director"."archive_type" IS '档案门类';
COMMENT ON COLUMN "public"."director"."category" IS '档案类别';
COMMENT ON COLUMN "public"."director"."doc_number" IS '档号';
COMMENT ON COLUMN "public"."director"."director_info" IS '目录信息';
COMMENT ON COLUMN "public"."director"."source" IS '目录来源';
COMMENT ON COLUMN "public"."director"."create_date" IS '创建时间';
COMMENT ON COLUMN "public"."director"."update_date" IS '更新时间';
COMMENT ON COLUMN "public"."director"."operator" IS '操作人';
COMMENT ON COLUMN "public"."director"."title" IS '题名';

-- ----------------------------
-- Records of director
-- ----------------------------

-- ----------------------------
-- Table structure for operation
-- ----------------------------
DROP TABLE IF EXISTS "public"."operation";
CREATE TABLE "public"."operation" (
  "id" int4 NOT NULL DEFAULT nextval('operation_id_seq'::regclass),
  "task_id" int4 NOT NULL,
  "task_name" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "operator" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "operator_date" timestamp(6) NOT NULL,
  "operator_remark" text COLLATE "pg_catalog"."default",
  "task_number_start" varchar(25) COLLATE "pg_catalog"."default",
  "task_number_end" varchar(25) COLLATE "pg_catalog"."default",
  "status" int4
)
;
COMMENT ON COLUMN "public"."operation"."id" IS 'ID';
COMMENT ON COLUMN "public"."operation"."task_id" IS '工作流ID';
COMMENT ON COLUMN "public"."operation"."task_name" IS '工作流名称';
COMMENT ON COLUMN "public"."operation"."operator" IS '操作人';
COMMENT ON COLUMN "public"."operation"."operator_date" IS '操作日期';
COMMENT ON COLUMN "public"."operation"."operator_remark" IS '备注';
COMMENT ON COLUMN "public"."operation"."status" IS '状态';

-- ----------------------------
-- Records of operation
-- ----------------------------

-- ----------------------------
-- Table structure for register
-- ----------------------------
DROP TABLE IF EXISTS "public"."register";
CREATE TABLE "public"."register" (
  "id" int4 NOT NULL DEFAULT nextval('register_id_seq'::regclass),
  "archive_type" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "category" varchar(25) COLLATE "pg_catalog"."default" NOT NULL,
  "batch_number" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "number_start" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "number_end" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "is_question" bool NOT NULL,
  "is_distribute" bool NOT NULL,
  "register" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "register_date" timestamp(6) NOT NULL,
  "status" int4 NOT NULL,
  "task_node" int4 NOT NULL,
  "is_import" bool NOT NULL
)
;
COMMENT ON COLUMN "public"."register"."id" IS 'ID';
COMMENT ON COLUMN "public"."register"."archive_type" IS '档案类别';
COMMENT ON COLUMN "public"."register"."category" IS '类型';
COMMENT ON COLUMN "public"."register"."batch_number" IS '批次号';
COMMENT ON COLUMN "public"."register"."number_start" IS '开始卷/件号';
COMMENT ON COLUMN "public"."register"."number_end" IS '终止卷/件号';
COMMENT ON COLUMN "public"."register"."is_question" IS '是否登记问题';
COMMENT ON COLUMN "public"."register"."is_distribute" IS '是否分配';
COMMENT ON COLUMN "public"."register"."register" IS '登记人';
COMMENT ON COLUMN "public"."register"."register_date" IS '登记日期';
COMMENT ON COLUMN "public"."register"."status" IS '状态; 0: 保存; 1:提交; 2:完结';
COMMENT ON COLUMN "public"."register"."task_node" IS '任务节点';
COMMENT ON COLUMN "public"."register"."is_import" IS '导入目录; 0: 未导入; 1: 已导入';

-- ----------------------------
-- Records of register
-- ----------------------------

-- ----------------------------
-- Table structure for register_question
-- ----------------------------
DROP TABLE IF EXISTS "public"."register_question";
CREATE TABLE "public"."register_question" (
  "id" int4 NOT NULL DEFAULT nextval('register_question_id_seq'::regclass),
  "register_id" int4 NOT NULL,
  "batch_number" varchar(50) COLLATE "pg_catalog"."default",
  "number_start" varchar(50) COLLATE "pg_catalog"."default",
  "number_end" varchar(50) COLLATE "pg_catalog"."default",
  "volume_number" varchar(25) COLLATE "pg_catalog"."default",
  "question_desc" text COLLATE "pg_catalog"."default",
  "recorder" varchar(50) COLLATE "pg_catalog"."default",
  "recorder_time" timestamp(6),
  "status" int4
)
;
COMMENT ON COLUMN "public"."register_question"."id" IS 'ID';
COMMENT ON COLUMN "public"."register_question"."register_id" IS '登记记录ID';
COMMENT ON COLUMN "public"."register_question"."batch_number" IS '批次号';
COMMENT ON COLUMN "public"."register_question"."number_start" IS '开始卷/件号';
COMMENT ON COLUMN "public"."register_question"."number_end" IS '终止卷/件号';
COMMENT ON COLUMN "public"."register_question"."volume_number" IS '卷/件号';
COMMENT ON COLUMN "public"."register_question"."question_desc" IS '问题描述';
COMMENT ON COLUMN "public"."register_question"."recorder" IS '记录人';
COMMENT ON COLUMN "public"."register_question"."recorder_time" IS '记录时间';
COMMENT ON COLUMN "public"."register_question"."status" IS '状态：0： 保存；1：提交';

-- ----------------------------
-- Records of register_question
-- ----------------------------

-- ----------------------------
-- Table structure for role_permission_association
-- ----------------------------
DROP TABLE IF EXISTS "public"."role_permission_association";
CREATE TABLE "public"."role_permission_association" (
  "role_id" int4 NOT NULL,
  "workflow_id" int4 NOT NULL
)
;

-- ----------------------------
-- Records of role_permission_association
-- ----------------------------
INSERT INTO "public"."role_permission_association" VALUES (1, 1);
INSERT INTO "public"."role_permission_association" VALUES (1, 2);
INSERT INTO "public"."role_permission_association" VALUES (1, 3);
INSERT INTO "public"."role_permission_association" VALUES (1, 4);
INSERT INTO "public"."role_permission_association" VALUES (1, 6);
INSERT INTO "public"."role_permission_association" VALUES (1, 7);
INSERT INTO "public"."role_permission_association" VALUES (1, 8);
INSERT INTO "public"."role_permission_association" VALUES (1, 9);
INSERT INTO "public"."role_permission_association" VALUES (1, 10);
INSERT INTO "public"."role_permission_association" VALUES (1, 11);
INSERT INTO "public"."role_permission_association" VALUES (1, 5);
INSERT INTO "public"."role_permission_association" VALUES (20, 1);
INSERT INTO "public"."role_permission_association" VALUES (20, 2);
INSERT INTO "public"."role_permission_association" VALUES (20, 3);
INSERT INTO "public"."role_permission_association" VALUES (20, 4);
INSERT INTO "public"."role_permission_association" VALUES (20, 5);
INSERT INTO "public"."role_permission_association" VALUES (20, 6);
INSERT INTO "public"."role_permission_association" VALUES (20, 7);
INSERT INTO "public"."role_permission_association" VALUES (20, 8);

-- ----------------------------
-- Table structure for roles
-- ----------------------------
DROP TABLE IF EXISTS "public"."roles";
CREATE TABLE "public"."roles" (
  "id" int4 NOT NULL DEFAULT nextval('roles_id_seq'::regclass),
  "name" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "desc" varchar(200) COLLATE "pg_catalog"."default",
  "is_active" bool,
  "create_time" timestamp(6),
  "update_time" timestamp(6)
)
;
COMMENT ON COLUMN "public"."roles"."id" IS '角色ID';
COMMENT ON COLUMN "public"."roles"."name" IS '角色名称（如：管理员、质检员、操作员）';
COMMENT ON COLUMN "public"."roles"."desc" IS '角色描述';
COMMENT ON COLUMN "public"."roles"."is_active" IS '是否激活';
COMMENT ON COLUMN "public"."roles"."create_time" IS '创建时间';
COMMENT ON COLUMN "public"."roles"."update_time" IS '更新时间';

-- ----------------------------
-- Records of roles
-- ----------------------------
INSERT INTO "public"."roles" VALUES (1, '管理员', '系统管理员', 't', '2026-03-17 03:05:13.688019', '2026-03-17 03:05:13.688019');
INSERT INTO "public"."roles" VALUES (20, '质检员', '加工系统全流程质检', 't', '2026-05-08 03:06:17.983684', '2026-05-08 03:07:25.465715');

-- ----------------------------
-- Table structure for scan
-- ----------------------------
DROP TABLE IF EXISTS "public"."scan";
CREATE TABLE "public"."scan" (
  "id" int4 NOT NULL DEFAULT nextval('scan_id_seq'::regclass),
  "task_id" int4 NOT NULL,
  "register_id" int4 NOT NULL,
  "dir_path" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "dir_name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "scan_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "scan_dpi" int4 NOT NULL,
  "scan_model" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "operator" varchar(50) COLLATE "pg_catalog"."default",
  "operator_date" timestamp(6),
  "file_count" int4 NOT NULL,
  "server_save_path" varchar(200) COLLATE "pg_catalog"."default"
)
;
COMMENT ON COLUMN "public"."scan"."id" IS 'ID';
COMMENT ON COLUMN "public"."scan"."task_id" IS '任务ID';
COMMENT ON COLUMN "public"."scan"."register_id" IS '登记ID';
COMMENT ON COLUMN "public"."scan"."dir_path" IS '扫描保存路径';
COMMENT ON COLUMN "public"."scan"."dir_name" IS '扫描文件夹名称';
COMMENT ON COLUMN "public"."scan"."scan_type" IS '扫描格式';
COMMENT ON COLUMN "public"."scan"."scan_dpi" IS '扫描分辨率dpi';
COMMENT ON COLUMN "public"."scan"."scan_model" IS '扫描色彩模式';
COMMENT ON COLUMN "public"."scan"."operator" IS '操作员';
COMMENT ON COLUMN "public"."scan"."operator_date" IS '操作日期';

-- ----------------------------
-- Records of scan
-- ----------------------------

-- ----------------------------
-- Table structure for scan_images
-- ----------------------------
DROP TABLE IF EXISTS "public"."scan_images";
CREATE TABLE "public"."scan_images" (
  "id" int4 NOT NULL DEFAULT nextval('scan_images_id_seq'::regclass),
  "scan_id" int4 NOT NULL,
  "file_name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "page_index" int4,
  "is_ocr" bool,
  "create_time" timestamp(6),
  "operator" varchar(20) COLLATE "pg_catalog"."default",
  "rec_text" text COLLATE "pg_catalog"."default"
)
;
COMMENT ON COLUMN "public"."scan_images"."id" IS 'ID';
COMMENT ON COLUMN "public"."scan_images"."scan_id" IS '扫描表ID';
COMMENT ON COLUMN "public"."scan_images"."file_name" IS '扫描文件名';
COMMENT ON COLUMN "public"."scan_images"."page_index" IS '当前页码';
COMMENT ON COLUMN "public"."scan_images"."is_ocr" IS '是否OCR';
COMMENT ON COLUMN "public"."scan_images"."create_time" IS '创建时间';
COMMENT ON COLUMN "public"."scan_images"."operator" IS '操作人';

-- ----------------------------
-- Records of scan_images
-- ----------------------------

-- ----------------------------
-- Table structure for task
-- ----------------------------
DROP TABLE IF EXISTS "public"."task";
CREATE TABLE "public"."task" (
  "id" int4 NOT NULL DEFAULT nextval('task_id_seq'::regclass),
  "task_id" int4 NOT NULL,
  "register_id" int4 NOT NULL,
  "batch_number" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "number_start" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "number_end" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "task_name" varchar(25) COLLATE "pg_catalog"."default" NOT NULL,
  "task_number_start" varchar(50) COLLATE "pg_catalog"."default",
  "task_number_end" varchar(50) COLLATE "pg_catalog"."default",
  "operator" varchar(50) COLLATE "pg_catalog"."default",
  "dist_officer" varchar(50) COLLATE "pg_catalog"."default",
  "dist_date" timestamp(6),
  "status" int4 NOT NULL,
  "is_ready" bool,
  "is_do" bool,
  "task_node" int4 NOT NULL,
  "operator_date" timestamp(6),
  "complete_number" varchar(50) COLLATE "pg_catalog"."default"
)
;
COMMENT ON COLUMN "public"."task"."id" IS 'ID';
COMMENT ON COLUMN "public"."task"."task_id" IS '任务id';
COMMENT ON COLUMN "public"."task"."register_id" IS '登记记录ID';
COMMENT ON COLUMN "public"."task"."batch_number" IS '批次号';
COMMENT ON COLUMN "public"."task"."number_start" IS '起始卷/件号';
COMMENT ON COLUMN "public"."task"."number_end" IS '截止卷/件号';
COMMENT ON COLUMN "public"."task"."task_name" IS '任务名称';
COMMENT ON COLUMN "public"."task"."task_number_start" IS '起始任务段号';
COMMENT ON COLUMN "public"."task"."task_number_end" IS '截止任务段号';
COMMENT ON COLUMN "public"."task"."operator" IS '操作员';
COMMENT ON COLUMN "public"."task"."dist_officer" IS '分配人';
COMMENT ON COLUMN "public"."task"."dist_date" IS '分配日期';
COMMENT ON COLUMN "public"."task"."status" IS '状态; 0: 保存; 1:提交;';
COMMENT ON COLUMN "public"."task"."is_ready" IS '前置任务是否已完成';
COMMENT ON COLUMN "public"."task"."is_do" IS '本任务是否完工';
COMMENT ON COLUMN "public"."task"."task_node" IS '任务节点';
COMMENT ON COLUMN "public"."task"."operator_date" IS '操作日期';

-- ----------------------------
-- Records of task
-- ----------------------------

-- ----------------------------
-- Table structure for task_mark
-- ----------------------------
DROP TABLE IF EXISTS "public"."task_mark";
CREATE TABLE "public"."task_mark" (
  "id" int4 NOT NULL DEFAULT nextval('task_mark_id_seq'::regclass),
  "task_id" int4 NOT NULL,
  "batch_number" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "task_node" int4 NOT NULL,
  "mark_stage" int4 NOT NULL,
  "scan_file" varchar(255) COLLATE "pg_catalog"."default",
  "page_no" int4,
  "field_name" varchar(100) COLLATE "pg_catalog"."default",
  "field_value_before" varchar(255) COLLATE "pg_catalog"."default",
  "mark_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "level" varchar(10) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "inspector" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "mark_date" timestamp(6) NOT NULL,
  "is_fixed" bool,
  "fix_date" timestamp(6),
  "fix_remark" text COLLATE "pg_catalog"."default",
  "field_value_after" varchar(255) COLLATE "pg_catalog"."default",
  "fix_people" varchar(255) COLLATE "pg_catalog"."default",
  "is_deleted" bool
)
;
COMMENT ON COLUMN "public"."task_mark"."id" IS '主键ID';
COMMENT ON COLUMN "public"."task_mark"."task_id" IS '关联任务ID';
COMMENT ON COLUMN "public"."task_mark"."batch_number" IS '批次号';
COMMENT ON COLUMN "public"."task_mark"."task_node" IS '任务节点号';
COMMENT ON COLUMN "public"."task_mark"."mark_stage" IS '质检阶段：1=扫描 2=图像处理 3=目录';
COMMENT ON COLUMN "public"."task_mark"."scan_file" IS '文件件名';
COMMENT ON COLUMN "public"."task_mark"."page_no" IS '页码';
COMMENT ON COLUMN "public"."task_mark"."field_name" IS '目录字段名, 如： 档号、题名等';
COMMENT ON COLUMN "public"."task_mark"."field_value_before" IS '目录字段原始值';
COMMENT ON COLUMN "public"."task_mark"."mark_type" IS '标记类型, 与 mark_stage 对应';
COMMENT ON COLUMN "public"."task_mark"."level" IS '严重程度：严重/一般/轻微';
COMMENT ON COLUMN "public"."task_mark"."description" IS '问题详细描述';
COMMENT ON COLUMN "public"."task_mark"."inspector" IS '质检员姓名';
COMMENT ON COLUMN "public"."task_mark"."mark_date" IS '标记时间';
COMMENT ON COLUMN "public"."task_mark"."is_fixed" IS '是否修改完成';
COMMENT ON COLUMN "public"."task_mark"."fix_date" IS '修改时间';
COMMENT ON COLUMN "public"."task_mark"."fix_remark" IS '修改说明：如：已重扫 第 7 页/ 更正档号';
COMMENT ON COLUMN "public"."task_mark"."field_value_after" IS '目录子段修改后的值';
COMMENT ON COLUMN "public"."task_mark"."is_deleted" IS '是否删除';

-- ----------------------------
-- Records of task_mark
-- ----------------------------

-- ----------------------------
-- Table structure for task_progress
-- ----------------------------
DROP TABLE IF EXISTS "public"."task_progress";
CREATE TABLE "public"."task_progress" (
  "id" int4 NOT NULL DEFAULT nextval('task_progress_id_seq'::regclass),
  "task_id" int4 NOT NULL,
  "sub_start" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "sub_end" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "status" int4,
  "operator" varchar(50) COLLATE "pg_catalog"."default",
  "operate_date" timestamp(6)
)
;
COMMENT ON COLUMN "public"."task_progress"."sub_start" IS '本次提交起始号';
COMMENT ON COLUMN "public"."task_progress"."sub_end" IS '本次提交截止号';
COMMENT ON COLUMN "public"."task_progress"."status" IS '0：保存；1：提交';

-- ----------------------------
-- Records of task_progress
-- ----------------------------

-- ----------------------------
-- Table structure for user_role_association
-- ----------------------------
DROP TABLE IF EXISTS "public"."user_role_association";
CREATE TABLE "public"."user_role_association" (
  "user_id" int4 NOT NULL,
  "role_id" int4 NOT NULL
)
;

-- ----------------------------
-- Records of user_role_association
-- ----------------------------
INSERT INTO "public"."user_role_association" VALUES (1, 1);
INSERT INTO "public"."user_role_association" VALUES (12, 20);

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS "public"."users";
CREATE TABLE "public"."users" (
  "id" int4 NOT NULL DEFAULT nextval('users_id_seq'::regclass),
  "username" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "password" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "is_active" bool,
  "create_time" timestamp(6),
  "update_time" timestamp(6),
  "last_login" timestamp(6)
)
;
COMMENT ON COLUMN "public"."users"."id" IS '用户ID';
COMMENT ON COLUMN "public"."users"."username" IS '用户名';
COMMENT ON COLUMN "public"."users"."password" IS '密码哈希（不存储明文）';
COMMENT ON COLUMN "public"."users"."is_active" IS '是否激活';
COMMENT ON COLUMN "public"."users"."create_time" IS '创建时间';
COMMENT ON COLUMN "public"."users"."update_time" IS '更新时间';
COMMENT ON COLUMN "public"."users"."last_login" IS '最近登录时间';

-- ----------------------------
-- Records of users
-- ----------------------------
INSERT INTO "public"."users" VALUES (1, 'admin', 'scrypt:32768:8:1$Hfur7uqxX5q4LR8m$36d0cf8ec89d8782700fc7c4496600702967b48ec8290609b3c5c051eb9969161c62d0278f545b10f379d1904798c7fec95a4bf6193c54ff030555528332c8d7', 't', '2026-03-17 03:06:20.500562', '2026-03-17 03:06:20.500562', '2026-07-08 10:56:20');
INSERT INTO "public"."users" VALUES (12, '质检', 'scrypt:32768:8:1$iOqfiYg1SCBtoTCr$59b7aa69a46c9dbcb00445e8e839368ab4bb6ee1e0e6ccb594bb380a6fe7d758aef117e74150a17b67d9ab2265010d4c5d3d9d86ad47c897f2e2ffd6469f6422', 't', '2026-05-08 03:22:04.151795', '2026-05-08 03:22:11.202283', '2026-05-08 03:22:11.200266');

-- ----------------------------
-- Table structure for workflows
-- ----------------------------
DROP TABLE IF EXISTS "public"."workflows";
CREATE TABLE "public"."workflows" (
  "id" int4 NOT NULL DEFAULT nextval('workflows_id_seq'::regclass),
  "work_name" varchar(25) COLLATE "pg_catalog"."default" NOT NULL,
  "status" bool,
  "is_work" int4
)
;
COMMENT ON COLUMN "public"."workflows"."id" IS '工作流索引';
COMMENT ON COLUMN "public"."workflows"."work_name" IS '工作流名称';
COMMENT ON COLUMN "public"."workflows"."status" IS '是否启用';
COMMENT ON COLUMN "public"."workflows"."is_work" IS '是否为工作流';

-- ----------------------------
-- Records of workflows
-- ----------------------------
INSERT INTO "public"."workflows" VALUES (6, '成品转换/输出', 't', 1);
INSERT INTO "public"."workflows" VALUES (3, '扫 描', 't', 1);
INSERT INTO "public"."workflows" VALUES (7, '目录录入/校对', 't', 1);
INSERT INTO "public"."workflows" VALUES (1, '领卷登记', 't', 0);
INSERT INTO "public"."workflows" VALUES (2, '拆卷/前处理', 't', 1);
INSERT INTO "public"."workflows" VALUES (4, '图像处理', 't', 1);
INSERT INTO "public"."workflows" VALUES (10, '统 计', 'f', 0);
INSERT INTO "public"."workflows" VALUES (11, '系统管理', 'f', 0);
INSERT INTO "public"."workflows" VALUES (5, '分 件', 't', 1);
INSERT INTO "public"."workflows" VALUES (8, '装 订', 't', 1);
INSERT INTO "public"."workflows" VALUES (9, '任务分发', 't', 0);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."archive_stamp_id_seq"
OWNED BY "public"."archive_stamp"."id";
SELECT setval('"public"."archive_stamp_id_seq"', 4, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."define_template_id_seq"
OWNED BY "public"."define_template"."id";
SELECT setval('"public"."define_template_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."director_id_seq"
OWNED BY "public"."director"."id";
SELECT setval('"public"."director_id_seq"', 1716, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."operation_id_seq"
OWNED BY "public"."operation"."id";
SELECT setval('"public"."operation_id_seq"', 1489, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."register_id_seq"
OWNED BY "public"."register"."id";
SELECT setval('"public"."register_id_seq"', 97, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."register_question_id_seq"
OWNED BY "public"."register_question"."id";
SELECT setval('"public"."register_question_id_seq"', 96, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."roles_id_seq"
OWNED BY "public"."roles"."id";
SELECT setval('"public"."roles_id_seq"', 20, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."scan_id_seq"
OWNED BY "public"."scan"."id";
SELECT setval('"public"."scan_id_seq"', 48, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."scan_images_id_seq"
OWNED BY "public"."scan_images"."id";
SELECT setval('"public"."scan_images_id_seq"', 104, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."task_id_seq"
OWNED BY "public"."task"."id";
SELECT setval('"public"."task_id_seq"', 521, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."task_mark_id_seq"
OWNED BY "public"."task_mark"."id";
SELECT setval('"public"."task_mark_id_seq"', 33, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."task_progress_id_seq"
OWNED BY "public"."task_progress"."id";
SELECT setval('"public"."task_progress_id_seq"', 46, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."users_id_seq"
OWNED BY "public"."users"."id";
SELECT setval('"public"."users_id_seq"', 12, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."workflows_id_seq"
OWNED BY "public"."workflows"."id";
SELECT setval('"public"."workflows_id_seq"', 1, false);

-- ----------------------------
-- Indexes structure for table archive_stamp
-- ----------------------------
CREATE INDEX "ix_archive_stamp_create_time" ON "public"."archive_stamp" USING btree (
  "create_time" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_archive_stamp_id" ON "public"."archive_stamp" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_archive_stamp_show_field_labels" ON "public"."archive_stamp" USING btree (
  "show_field_labels" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_archive_stamp_template_name" ON "public"."archive_stamp" USING btree (
  "template_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_archive_stamp_update_time" ON "public"."archive_stamp" USING btree (
  "update_time" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table archive_stamp
-- ----------------------------
ALTER TABLE "public"."archive_stamp" ADD CONSTRAINT "archive_stamp_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table define_template
-- ----------------------------
CREATE INDEX "ix_define_template_create_date" ON "public"."define_template" USING btree (
  "create_date" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_define_template_creator" ON "public"."define_template" USING btree (
  "creator" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_define_template_field_info" ON "public"."define_template" USING btree (
  "field_info" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_define_template_id" ON "public"."define_template" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_define_template_template_name" ON "public"."define_template" USING btree (
  "template_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table define_template
-- ----------------------------
ALTER TABLE "public"."define_template" ADD CONSTRAINT "define_template_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table director
-- ----------------------------
CREATE INDEX "ix_director_archive_type" ON "public"."director" USING btree (
  "archive_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_director_category" ON "public"."director" USING btree (
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_director_create_date" ON "public"."director" USING btree (
  "create_date" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_director_director_info" ON "public"."director" USING btree (
  "director_info" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_director_doc_number" ON "public"."director" USING btree (
  "doc_number" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_director_id" ON "public"."director" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_director_operator" ON "public"."director" USING btree (
  "operator" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_director_register_id" ON "public"."director" USING btree (
  "register_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_director_source" ON "public"."director" USING btree (
  "source" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_director_update_date" ON "public"."director" USING btree (
  "update_date" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table director
-- ----------------------------
ALTER TABLE "public"."director" ADD CONSTRAINT "director_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table operation
-- ----------------------------
CREATE INDEX "ix_operation_id" ON "public"."operation" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_operation_name_id" ON "public"."operation" USING btree (
  "task_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_operation_operator" ON "public"."operation" USING btree (
  "operator" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_operation_operator_date" ON "public"."operation" USING btree (
  "operator_date" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_operation_operator_remark" ON "public"."operation" USING btree (
  "operator_remark" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_operation_task_name" ON "public"."operation" USING btree (
  "task_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table operation
-- ----------------------------
ALTER TABLE "public"."operation" ADD CONSTRAINT "operation_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table register
-- ----------------------------
CREATE INDEX "ix_register_archive_type" ON "public"."register" USING btree (
  "archive_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_batch_number" ON "public"."register" USING btree (
  "batch_number" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_category" ON "public"."register" USING btree (
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_id" ON "public"."register" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_is_distribute" ON "public"."register" USING btree (
  "is_distribute" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_is_import" ON "public"."register" USING btree (
  "is_import" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_is_question" ON "public"."register" USING btree (
  "is_question" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_number_end" ON "public"."register" USING btree (
  "number_end" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_number_start" ON "public"."register" USING btree (
  "number_start" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_register" ON "public"."register" USING btree (
  "register" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_register_date" ON "public"."register" USING btree (
  "register_date" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_status" ON "public"."register" USING btree (
  "status" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_task_node" ON "public"."register" USING btree (
  "task_node" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table register
-- ----------------------------
ALTER TABLE "public"."register" ADD CONSTRAINT "register_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table register_question
-- ----------------------------
CREATE INDEX "ix_register_question_batch_number" ON "public"."register_question" USING btree (
  "batch_number" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_question_id" ON "public"."register_question" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_question_number_end" ON "public"."register_question" USING btree (
  "number_end" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_question_number_start" ON "public"."register_question" USING btree (
  "number_start" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_question_question_desc" ON "public"."register_question" USING btree (
  "question_desc" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_question_recorder" ON "public"."register_question" USING btree (
  "recorder" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_question_recorder_time" ON "public"."register_question" USING btree (
  "recorder_time" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_question_register_id" ON "public"."register_question" USING btree (
  "register_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_register_question_volume_number" ON "public"."register_question" USING btree (
  "volume_number" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table register_question
-- ----------------------------
ALTER TABLE "public"."register_question" ADD CONSTRAINT "register_question_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table role_permission_association
-- ----------------------------
ALTER TABLE "public"."role_permission_association" ADD CONSTRAINT "role_permission_association_pkey" PRIMARY KEY ("role_id", "workflow_id");

-- ----------------------------
-- Indexes structure for table roles
-- ----------------------------
CREATE INDEX "ix_roles_id" ON "public"."roles" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_roles_name" ON "public"."roles" USING btree (
  "name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table roles
-- ----------------------------
ALTER TABLE "public"."roles" ADD CONSTRAINT "roles_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table scan
-- ----------------------------
CREATE INDEX "ix_scan_dir_name" ON "public"."scan" USING btree (
  "dir_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scan_dir_path" ON "public"."scan" USING btree (
  "dir_path" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scan_id" ON "public"."scan" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scan_operator" ON "public"."scan" USING btree (
  "operator" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scan_operator_date" ON "public"."scan" USING btree (
  "operator_date" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scan_register_id" ON "public"."scan" USING btree (
  "register_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scan_scan_dpi" ON "public"."scan" USING btree (
  "scan_dpi" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scan_scan_model" ON "public"."scan" USING btree (
  "scan_model" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scan_scan_type" ON "public"."scan" USING btree (
  "scan_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scan_task_id" ON "public"."scan" USING btree (
  "task_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table scan
-- ----------------------------
ALTER TABLE "public"."scan" ADD CONSTRAINT "scan_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table scan_images
-- ----------------------------
CREATE INDEX "idx_scan_id" ON "public"."scan_images" USING btree (
  "scan_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scan_images_create_time" ON "public"."scan_images" USING btree (
  "create_time" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scan_images_operator" ON "public"."scan_images" USING btree (
  "operator" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scan_images_scan_id" ON "public"."scan_images" USING btree (
  "scan_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table scan_images
-- ----------------------------
ALTER TABLE "public"."scan_images" ADD CONSTRAINT "scan_images_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table task
-- ----------------------------
CREATE INDEX "idx_batch_node_status" ON "public"."task" USING btree (
  "batch_number" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "task_node" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "status" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_range_lookup" ON "public"."task" USING btree (
  "batch_number" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "task_node" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "task_number_start" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "task_number_end" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_batch_number" ON "public"."task" USING btree (
  "batch_number" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_dist_date" ON "public"."task" USING btree (
  "dist_date" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_dist_officer" ON "public"."task" USING btree (
  "dist_officer" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_id" ON "public"."task" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_number_end" ON "public"."task" USING btree (
  "number_end" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_number_start" ON "public"."task" USING btree (
  "number_start" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_operator" ON "public"."task" USING btree (
  "operator" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_operator_date" ON "public"."task" USING btree (
  "operator_date" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_register_id" ON "public"."task" USING btree (
  "register_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_status" ON "public"."task" USING btree (
  "status" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_task_id" ON "public"."task" USING btree (
  "task_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_task_name" ON "public"."task" USING btree (
  "task_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_task_node" ON "public"."task" USING btree (
  "task_node" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_task_number_end" ON "public"."task" USING btree (
  "task_number_end" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_task_number_start" ON "public"."task" USING btree (
  "task_number_start" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table task
-- ----------------------------
ALTER TABLE "public"."task" ADD CONSTRAINT "task_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table task_mark
-- ----------------------------
CREATE INDEX "ix_task_mark_batch_number" ON "public"."task_mark" USING btree (
  "batch_number" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_mark_inspector" ON "public"."task_mark" USING btree (
  "inspector" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_mark_mark_date" ON "public"."task_mark" USING btree (
  "mark_date" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_mark_mark_stage" ON "public"."task_mark" USING btree (
  "mark_stage" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_mark_task_id" ON "public"."task_mark" USING btree (
  "task_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_mark_task_node" ON "public"."task_mark" USING btree (
  "task_node" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table task_mark
-- ----------------------------
ALTER TABLE "public"."task_mark" ADD CONSTRAINT "task_mark_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table task_progress
-- ----------------------------
CREATE INDEX "ix_task_progress_operate_date" ON "public"."task_progress" USING btree (
  "operate_date" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_progress_operator" ON "public"."task_progress" USING btree (
  "operator" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table task_progress
-- ----------------------------
ALTER TABLE "public"."task_progress" ADD CONSTRAINT "task_progress_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table user_role_association
-- ----------------------------
ALTER TABLE "public"."user_role_association" ADD CONSTRAINT "user_role_association_pkey" PRIMARY KEY ("user_id", "role_id");

-- ----------------------------
-- Indexes structure for table users
-- ----------------------------
CREATE INDEX "ix_users_id" ON "public"."users" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_users_username" ON "public"."users" USING btree (
  "username" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table users
-- ----------------------------
ALTER TABLE "public"."users" ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table workflows
-- ----------------------------
CREATE INDEX "ix_workflows_id" ON "public"."workflows" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_workflows_work_name" ON "public"."workflows" USING btree (
  "work_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table workflows
-- ----------------------------
ALTER TABLE "public"."workflows" ADD CONSTRAINT "workflows_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Foreign Keys structure for table register_question
-- ----------------------------
ALTER TABLE "public"."register_question" ADD CONSTRAINT "register_question_register_id_fkey" FOREIGN KEY ("register_id") REFERENCES "public"."register" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table role_permission_association
-- ----------------------------
ALTER TABLE "public"."role_permission_association" ADD CONSTRAINT "role_permission_association_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "public"."roles" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."role_permission_association" ADD CONSTRAINT "role_permission_association_workflow_id_fkey" FOREIGN KEY ("workflow_id") REFERENCES "public"."workflows" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table scan
-- ----------------------------
ALTER TABLE "public"."scan" ADD CONSTRAINT "scan_register_id_fkey" FOREIGN KEY ("register_id") REFERENCES "public"."register" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."scan" ADD CONSTRAINT "scan_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "public"."task" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table scan_images
-- ----------------------------
ALTER TABLE "public"."scan_images" ADD CONSTRAINT "scan_images_scan_id_fkey" FOREIGN KEY ("scan_id") REFERENCES "public"."scan" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table task
-- ----------------------------
ALTER TABLE "public"."task" ADD CONSTRAINT "task_register_id_fkey" FOREIGN KEY ("register_id") REFERENCES "public"."register" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table task_mark
-- ----------------------------
ALTER TABLE "public"."task_mark" ADD CONSTRAINT "task_mark_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "public"."task" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table task_progress
-- ----------------------------
ALTER TABLE "public"."task_progress" ADD CONSTRAINT "task_progress_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "public"."task" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table user_role_association
-- ----------------------------
ALTER TABLE "public"."user_role_association" ADD CONSTRAINT "user_role_association_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "public"."roles" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."user_role_association" ADD CONSTRAINT "user_role_association_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
