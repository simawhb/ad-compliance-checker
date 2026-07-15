-- ============================================================================
-- 驷马报考 (Gaokao Database) — 建库建表脚本
-- ============================================================================
-- 项目:  高考志愿填报数据库
-- 目标:  建立覆盖全国高校、专业、历年录取、招生政策、就业、排名及
--        用户口碑的全维度数据库
-- 数据库: PostgreSQL 16+
-- 编码:   UTF8, LC_COLLATE = 'zh_CN.UTF-8'
-- 日期:   2026-06-29
-- 版本:   v1.0
-- ============================================================================
-- 使用方法:
--   1. 以超级用户连接 PostgreSQL:
--        psql -h localhost -U postgres
--   2. 执行本脚本:
--        \i D:/WorkBuddy/gaokao-database/src/scripts/init_db.sql
--   3. 每年新增录取分区请使用:
--        src/scripts/create_partitions.sql
-- ============================================================================
-- Schema 分区说明:
--   base          基础数据（院校、专业）
--   admission     录取数据（投档线、省控线、一分一段）
--   policy        招生政策数据
--   employment    就业数据（统计、报告、地域招聘）
--   ranking       排名数据（软科、校友会、QS 等）
--   user_content  用户评价与口碑
--   meta          元数据（采集任务、变更日志、附件）
--   monitor       监控（网站巡检）
-- ============================================================================

-- ============================================================================
-- 0. 数据库创建（需要以 superuser 执行，单独运行）
-- ============================================================================
-- 注意：以下语句需要在 psql 中以超级用户身份单独执行，
--       不能在事务块中运行。使用时请取消注释。
--
-- CREATE DATABASE gaokao_db
--     WITH ENCODING 'UTF8'
--     LC_COLLATE = 'zh_CN.UTF-8'
--     LC_CTYPE = 'zh_CN.UTF-8'
--     TEMPLATE = template0;
--
-- COMMENT ON DATABASE gaokao_db IS '驷马报考 — 高考志愿填报全维度数据库';
-- ============================================================================

-- 连接到 gaokao_db 后执行以下内容：
-- \c gaokao_db

-- ============================================================================
-- 1. 扩展
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;            -- 模糊搜索（trigram索引）
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;  -- 查询性能分析
-- CREATE EXTENSION IF NOT EXISTS pg_cron;          -- 定时任务（按需启用）

-- ============================================================================
-- 2. Schema 创建
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS base;           -- 基础数据：院校、专业
COMMENT ON SCHEMA base IS '基础数据：院校信息、专业目录';

CREATE SCHEMA IF NOT EXISTS admission;      -- 录取数据
COMMENT ON SCHEMA admission IS '录取数据：投档线、省控线、一分一段';

CREATE SCHEMA IF NOT EXISTS policy;         -- 政策数据
COMMENT ON SCHEMA policy IS '政策数据：招生政策、投档规则';

CREATE SCHEMA IF NOT EXISTS employment;     -- 就业数据
COMMENT ON SCHEMA employment IS '就业数据：就业统计、质量报告、地域招聘';

CREATE SCHEMA IF NOT EXISTS ranking;        -- 排名数据
COMMENT ON SCHEMA ranking IS '排名数据：软科、校友会、QS、学科评估等';

CREATE SCHEMA IF NOT EXISTS user_content;   -- 用户评价
COMMENT ON SCHEMA user_content IS '用户内容：评价、论坛长帖、口碑指数';

CREATE SCHEMA IF NOT EXISTS meta;           -- 元数据
COMMENT ON SCHEMA meta IS '元数据：采集任务、变更日志、文件附件';

CREATE SCHEMA IF NOT EXISTS monitor;        -- 监控
COMMENT ON SCHEMA monitor IS '监控：网站巡检日志、数据质量告警';

-- ============================================================================
-- 3. 基础数据层 (base) — 院校、专业
-- ============================================================================

-- ----------------------------------------------------------------------------
-- base.schools — 院校基础信息表
-- 数据来源：教育部全国高等学校名单、阳光高考院校库
-- 主键：code_edu（教育部院校代码，5 位数字，唯一）
-- ----------------------------------------------------------------------------
CREATE TABLE base.schools (
    code_edu              VARCHAR(10)   PRIMARY KEY,   -- 教育部院校代码（5位数字，唯一标识）
    name                  VARCHAR(200)  NOT NULL,      -- 院校全称（如"北京大学"）
    name_aliases          JSONB,                       -- 曾用名/别名（JSON数组，如["北京医科大学（合并前）"]）
    name_en               VARCHAR(300),                -- 英文名称
    code_gaokao           JSONB,                       -- 高考院校代码（各省不同，JSON对象按省份存储）
    code_yb               VARCHAR(20),                 -- 研招网代码
    level                 VARCHAR(20),                 -- 办学层次（本科/专科/职业本科）
    type                  VARCHAR(20),                 -- 办学类型（综合/理工/农林/医药/师范/语言/财经/政法/体育/艺术/军事/民族）
    category              VARCHAR(30),                 -- 院校类别（普通院校/211/985/双一流/军校/中外合作/港澳）
    is_211                BOOLEAN       DEFAULT FALSE, -- 是否为211工程
    is_985                BOOLEAN       DEFAULT FALSE, -- 是否为985工程
    is_double_first_class BOOLEAN       DEFAULT FALSE, -- 是否为双一流
    double_first_class_round INTEGER,                 -- 双一流批次（1/2）
    admin_department      VARCHAR(100),                -- 主管部门（教育部/工信部/陕西省/…）
    province              VARCHAR(30),                 -- 所在省份
    city                  VARCHAR(50),                 -- 所在城市
    district              VARCHAR(50),                 -- 所在区县
    address               VARCHAR(500),                -- 详细地址
    postal_code           VARCHAR(10),                 -- 邮政编码
    website               VARCHAR(500),                -- 官网URL
    admission_office_phone VARCHAR(50),                -- 招生办电话
    admission_office_website VARCHAR(500),             -- 招生网URL
    email                 VARCHAR(200),                -- 招生邮箱
    logo_url              VARCHAR(1000),               -- 校徽URL
    thumbnail_url         VARCHAR(1000),               -- 校门图片URL
    established_year      INTEGER,                     -- 建校年份
    history               TEXT,                        -- 校史简介
    area_acre             NUMERIC(8,2),                -- 占地面积（亩）
    student_undergrad     INTEGER,                     -- 本科生人数
    student_postgrad      INTEGER,                     -- 研究生人数
    student_total         INTEGER,                     -- 在校生总数
    faculty_count         INTEGER,                     -- 教职工总数
    faculty_professor     INTEGER,                     -- 教授人数
    library_volume        NUMERIC(8,2),                -- 图书馆藏书量（万册）
    campus_count          INTEGER,                     -- 校区数量
    campus_info           JSONB,                       -- 校区信息（JSON：名称+地址+专业分布）
    academician_count     INTEGER,                     -- 两院院士人数
    doctoral_programs     INTEGER,                     -- 博士点数量
    master_programs       INTEGER,                     -- 硕士点数量
    key_labs              JSONB,                       -- 国家重点实验室（JSON数组）
    features              JSONB,                       -- 办学特色标签（JSON数组）
    scholarship_info      TEXT,                        -- 奖助学金信息
    tuition_range         JSONB,                       -- 学费范围（JSON: {min, max, average}）
    accommodation         TEXT,                        -- 住宿条件描述
    accommodation_fee     VARCHAR(200),                -- 住宿费范围
    data_source           VARCHAR(200),                -- 数据来源标记
    data_version          INTEGER,                     -- 数据版本/年份
    created_at            TIMESTAMP     DEFAULT NOW(), -- 记录创建时间
    updated_at            TIMESTAMP     DEFAULT NOW()  -- 记录更新时间
);

-- ----------------------------------------------------------------------------
-- base.major_categories — 学科门类表
-- 数据来源：教育部学科门类目录（本科/专科）
-- 支持多级分类（如：工学 → 计算机类 → 计算机科学与技术）
-- ----------------------------------------------------------------------------
CREATE TABLE base.major_categories (
    category_id    SERIAL        PRIMARY KEY,   -- 学科门类ID（自增）
    category_name  VARCHAR(100)  NOT NULL,      -- 学科门类名称（如"工学"）
    category_code  VARCHAR(10)   NOT NULL,      -- 学科门类代码（如"08"）
    level          VARCHAR(10)   DEFAULT '本科', -- 层次（本科/专科）
    parent_id      INTEGER,                     -- 上级类别ID（支持多级分类，NULL表示顶级门类）
    created_at     TIMESTAMP     DEFAULT NOW(),
    updated_at     TIMESTAMP     DEFAULT NOW(),
    UNIQUE (category_code, level)
);

-- ----------------------------------------------------------------------------
-- base.majors — 专业目录表
-- 数据来源：教育部本科/专科专业目录（年度发布）
-- 主键：(major_id, version_year) — 同一专业代码跨年可有微调
-- ----------------------------------------------------------------------------
CREATE TABLE base.majors (
    major_id            VARCHAR(20)  NOT NULL,      -- 专业ID（教育部专业代码）
    name                VARCHAR(200) NOT NULL,      -- 专业名称
    name_full           VARCHAR(300),               -- 专业全称（含方向）
    category_id         INTEGER,                    -- 所属学科门类ID
    subject_group       VARCHAR(100),               -- 选科要求（3+1+2模式）
    subject_group_3p3   VARCHAR(100),               -- 选科要求（3+3模式）
    level               VARCHAR(10)  DEFAULT '本科',-- 学历层次（本科/专科）
    study_years         INTEGER      DEFAULT 4,     -- 修业年限（4年/5年/3年）
    degree              VARCHAR(100),               -- 授予学位（工学学士/理学学士/…）
    description         TEXT,                       -- 专业简介
    main_courses        JSONB,                      -- 主干课程（JSON数组）
    typical_schools     INTEGER,                    -- 开设此专业的典型院校数
    employment_rate     NUMERIC(5,2),               -- 全国平均就业率（最新，百分比）
    employment_direction TEXT,                      -- 就业方向描述
    salary_avg          NUMERIC(8,2),               -- 全国平均薪资（元/月）
    is_special          BOOLEAN      DEFAULT FALSE, -- 是否国家特色专业
    special_label       VARCHAR(100),               -- 特色标签（国家一流/省级一流/卓工/…）
    version_year        INTEGER      NOT NULL,      -- 专业目录版本年份（如2024）
    created_at          TIMESTAMP    DEFAULT NOW(),
    updated_at          TIMESTAMP    DEFAULT NOW(),
    PRIMARY KEY (major_id, version_year)
);

-- ============================================================================
-- 4. 录取数据层 (admission) — 投档线、省控线、一分一段
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 序列：录取数据共享ID序列（分区表跨分区唯一ID）
-- ----------------------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS admission.admission_data_id_seq;

-- ----------------------------------------------------------------------------
-- admission.admission_data — 历年录取数据（核心大表，按年份分区）
-- 数据来源：各省教育考试院公布的投档线
-- 去重键：(school_id, major_id, province, year, batch, student_category)
-- 注意：PRIMARY KEY 必须包含 year 以支持分区
-- ----------------------------------------------------------------------------
CREATE TABLE admission.admission_data (
    id                BIGINT        NOT NULL DEFAULT nextval('admission.admission_data_id_seq'),
    year              INTEGER       NOT NULL,                -- 录取年份
    school_id         VARCHAR(10)   NOT NULL,                -- 院校ID（参照 base.schools.code_edu）
    major_id          VARCHAR(20),                           -- 专业ID（若为院校投档线则填 NULL）
    province          VARCHAR(20)   NOT NULL,                -- 省份
    city_area         VARCHAR(50),                           -- 所属地区（部分省份分地市招生）
    batch             VARCHAR(50),                           -- 批次名称（本科一批/本科二批/专科批/提前批/…）
    batch_category    VARCHAR(50),                           -- 批次类别（普通类/艺术类/体育类/强基计划/…）
    student_category  VARCHAR(20),                           -- 考生类别（文科/理科/综合/物理类/历史类/不分文理）
    plan_count        INTEGER,                               -- 计划招生人数
    admit_count       INTEGER,                               -- 实际录取人数
    admit_score_min   NUMERIC(5,1),                          -- 最低录取分数
    admit_score_avg   NUMERIC(5,1),                          -- 平均录取分数
    admit_score_max   NUMERIC(5,1),                          -- 最高录取分数
    admit_score_diff  NUMERIC(5,1),                          -- 线差（最低分 - 批次线）
    admit_rank_min    INTEGER,                               -- 最低录取位次
    admit_rank_avg    INTEGER,                               -- 平均录取位次
    batch_score_line  NUMERIC(5,1),                          -- 对应批次省控线
    score_calculation VARCHAR(50),                           -- 总分计算方式（含听力/不含听力/750/…）
    is_racial         BOOLEAN       DEFAULT FALSE,           -- 是否少数民族预科/定向等特殊类型
    remark            TEXT,                                  -- 备注（如"含定向西藏就业"）
    data_source       VARCHAR(200),                          -- 数据来源（省考试院/阳光高考/…）
    data_confidence   VARCHAR(10)   DEFAULT 'medium',        -- 数据可信度（high/medium/low）
    created_at        TIMESTAMP     DEFAULT NOW(),
    updated_at        TIMESTAMP     DEFAULT NOW(),
    CONSTRAINT pk_admission_data PRIMARY KEY (id, year)
) PARTITION BY RANGE (year);

-- ----------------------------------------------------------------------------
-- 录取数据分区：admission_2022 ~ admission_2025
-- ----------------------------------------------------------------------------
CREATE TABLE admission.admission_2022 PARTITION OF admission.admission_data
    FOR VALUES FROM (2022) TO (2023);
COMMENT ON TABLE admission.admission_2022 IS '录取数据 — 2022年分区';

CREATE TABLE admission.admission_2023 PARTITION OF admission.admission_data
    FOR VALUES FROM (2023) TO (2024);
COMMENT ON TABLE admission.admission_2023 IS '录取数据 — 2023年分区';

CREATE TABLE admission.admission_2024 PARTITION OF admission.admission_data
    FOR VALUES FROM (2024) TO (2025);
COMMENT ON TABLE admission.admission_2024 IS '录取数据 — 2024年分区';

CREATE TABLE admission.admission_2025 PARTITION OF admission.admission_data
    FOR VALUES FROM (2025) TO (2026);
COMMENT ON TABLE admission.admission_2025 IS '录取数据 — 2025年分区';

-- ----------------------------------------------------------------------------
-- admission.province_score_lines — 省控线表
-- 数据来源：各省教育考试院公布的高考批次分数线
-- 去重键：(province, year, batch, student_category)
-- ----------------------------------------------------------------------------
CREATE TABLE admission.province_score_lines (
    id                SERIAL        PRIMARY KEY,
    province          VARCHAR(20)   NOT NULL,      -- 省份
    year              INTEGER       NOT NULL,      -- 年份
    batch             VARCHAR(50)   NOT NULL,      -- 批次（本科一批/本科二批/专科批/…）
    student_category  VARCHAR(20)   NOT NULL,      -- 考生类别（文科/理科/物理类/历史类/…）
    score_line        NUMERIC(5,1)  NOT NULL,      -- 批次分数线
    created_at        TIMESTAMP     DEFAULT NOW(),
    updated_at        TIMESTAMP     DEFAULT NOW(),
    UNIQUE (province, year, batch, student_category)
);

-- ----------------------------------------------------------------------------
-- admission.score_rank_segments — 一分一段表
-- 数据来源：各省教育考试院公布的高考成绩分段统计
-- 去重键：(province, year, student_category, score)
-- ----------------------------------------------------------------------------
CREATE TABLE admission.score_rank_segments (
    id                SERIAL        PRIMARY KEY,
    province          VARCHAR(20)   NOT NULL,      -- 省份
    year              INTEGER       NOT NULL,      -- 年份
    student_category  VARCHAR(20)   NOT NULL,      -- 考生类别
    score             INTEGER       NOT NULL,      -- 分数
    rank_start        INTEGER,                     -- 该分起始位次（累计人数上界）
    rank_end          INTEGER,                     -- 该分结束位次（累计人数下界）
    same_score_count  INTEGER,                     -- 同分人数
    cumulative_count  INTEGER,                     -- 累计人数（>= 该分）
    data_source       VARCHAR(200),                -- 数据来源
    created_at        TIMESTAMP     DEFAULT NOW(),
    updated_at        TIMESTAMP     DEFAULT NOW(),
    UNIQUE (province, year, student_category, score)
);

-- ============================================================================
-- 5. 政策数据层 (policy) — 招生政策
-- ============================================================================

-- ----------------------------------------------------------------------------
-- policy.policies — 招生政策表
-- 数据来源：各省教育考试院 / 教育部发布的招生工作规定
-- ----------------------------------------------------------------------------
CREATE TABLE policy.policies (
    id                SERIAL        PRIMARY KEY,
    province          VARCHAR(20)   NOT NULL,      -- 发布省份（"全国"表示教育部文件）
    year              INTEGER       NOT NULL,      -- 适用年份
    title             VARCHAR(500)  NOT NULL,      -- 文件标题
    document_type     VARCHAR(50),                 -- 文件类型（招生工作规定/志愿填报须知/投档规则/…）
    url               VARCHAR(1000),               -- 原文URL
    content_text      TEXT,                        -- 文本内容（markdown 格式）
    content_html      TEXT,                        -- HTML 原始内容
    summary           VARCHAR(500),                -- AI 自动摘要（200字以内）
    key_points        JSONB,                       -- 关键点提取（JSON数组）
    batch_settings    JSONB,                       -- 批次设置详情（JSON）
    voting_rule       VARCHAR(50),                 -- 投档规则（平行志愿/顺序志愿/…）
    voting_ratio      VARCHAR(20),                 -- 投档比例
    admission_rule    VARCHAR(50),                 -- 录取规则（分数优先/专业优先/专业级差/…）
    admission_ratio   VARCHAR(20),                 -- 提档比例
    policy_changes    JSONB,                       -- 与上年变化（JSON，字段级变化描述）
    tags              JSONB,                       -- 标签（"新高考改革"/"批次合并"/"专项计划"/…）
    data_source       VARCHAR(200),                -- 数据来源
    created_at        TIMESTAMP     DEFAULT NOW(),
    updated_at        TIMESTAMP     DEFAULT NOW()
);

-- ============================================================================
-- 6. 就业数据层 (employment) — 就业统计、报告、地域招聘
-- ============================================================================

-- ----------------------------------------------------------------------------
-- employment.employment_stats — 就业统计数据表
-- 数据来源：各高校就业质量报告、第三方数据（麦可思等）
-- school_id 和 major_id 至少一个不为 NULL
-- ----------------------------------------------------------------------------
CREATE TABLE employment.employment_stats (
    id                         SERIAL        PRIMARY KEY,
    school_id                  VARCHAR(10),                -- 院校ID（可为NULL，参照 base.schools.code_edu）
    major_id                   VARCHAR(20),                -- 专业ID（可为NULL，至少一个不为NULL）
    year                       INTEGER       NOT NULL,     -- 统计年份
    province                   VARCHAR(30),                -- 所在省份（可为NULL表示全国）
    employment_rate            NUMERIC(5,2),               -- 就业率（百分比）
    employment_rate_profession NUMERIC(5,2),               -- 专业对口率（百分比）
    salary_avg                 NUMERIC(8,2),               -- 平均月薪
    salary_median              NUMERIC(8,2),               -- 月薪中位数
    salary_top_25              NUMERIC(8,2),               -- 前25%月薪
    salary_bottom_25           NUMERIC(8,2),               -- 后25%月薪
    industry_top3              JSONB,                      -- 主要就业行业TOP3（JSON数组）
    employer_top5              JSONB,                      -- 主要就业单位TOP5（JSON数组）
    city_distribution          JSONB,                      -- 就业城市分布（JSON，如 {"北京":"30%", "上海":"20%"}）
    further_study_rate         NUMERIC(5,2),               -- 升学率（读研/读博，百分比）
    overseas_rate              NUMERIC(5,2),               -- 出国率（百分比）
    data_source                VARCHAR(200),               -- 来源（学校/教育部/第三方）
    created_at                 TIMESTAMP     DEFAULT NOW(),
    updated_at                 TIMESTAMP     DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- employment.regional_job_stats — 地域招聘 × 专业关联表 (README.md 新增)
-- 数据来源：BOSS直聘、智联招聘等平台的公开搜索统计
-- 目标：建立「专业 × 城市 × 薪资/岗位数」的关联数据库
-- 去重键：(major_id, city, platform, year, month)
-- ----------------------------------------------------------------------------
CREATE TABLE employment.regional_job_stats (
    id                       SERIAL        PRIMARY KEY,
    major_id                 VARCHAR(20),                  -- 专业ID
    major_name               VARCHAR(100),                 -- 专业名称
    city                     VARCHAR(50)   NOT NULL,       -- 城市
    province                 VARCHAR(20)   NOT NULL,       -- 省份
    year                     INTEGER       NOT NULL DEFAULT 2026, -- 数据年份
    month                    INTEGER       NOT NULL DEFAULT 1,    -- 数据月份
    -- 岗位数据
    total_job_count          INTEGER,                      -- 总岗位数
    avg_salary               NUMERIC(8,2),                 -- 平均薪资（元/月）
    median_salary            NUMERIC(8,2),                 -- 薪资中位数
    salary_min               NUMERIC(8,2),                 -- 薪资低端
    salary_max               NUMERIC(8,2),                 -- 薪资高端
    -- 岗位结构
    top_job_titles           JSONB,                        -- 热招岗位 TOP10
    degree_requirement       JSONB,                        -- 学历要求分布
    experience_requirement   JSONB,                        -- 经验要求分布
    industry_distribution    JSONB,                        -- 行业分布
    -- 元数据
    platform                 VARCHAR(50),                  -- 招聘平台（BOSS直聘/智联/前程无忧）
    data_source              VARCHAR(200),                 -- 数据来源
    created_at               TIMESTAMP     DEFAULT NOW(),
    updated_at               TIMESTAMP     DEFAULT NOW(),
    UNIQUE (major_id, city, platform, year, month)
);

-- ----------------------------------------------------------------------------
-- employment.employment_reports — 就业质量报告表
-- 数据来源：各高校就业网发布的年度就业质量报告（PDF）
-- ----------------------------------------------------------------------------
CREATE TABLE employment.employment_reports (
    id                SERIAL        PRIMARY KEY,
    school_id         VARCHAR(10)   NOT NULL,      -- 院校ID（参照 base.schools.code_edu）
    year              INTEGER       NOT NULL,      -- 报告年份
    title             VARCHAR(500),                -- 报告标题
    url               VARCHAR(1000),               -- 报告原文URL（学校就业网）
    file_url          VARCHAR(1000),               -- PDF附件URL
    summary           TEXT,                        -- AI摘要
    key_metrics       JSONB,                       -- 关键指标（JSON）
    has_attachment    BOOLEAN       DEFAULT FALSE, -- 是否有PDF附件
    created_at        TIMESTAMP     DEFAULT NOW(),
    updated_at        TIMESTAMP     DEFAULT NOW()
);

-- ============================================================================
-- 7. 排名数据层 (ranking) — 各类排名
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ranking.rankings — 排名数据表
-- 数据来源：软科、校友会、QS、US News、泰晤士、ESI、教育部学科评估
-- 去重键：(ranking_name, ranking_year, school_id, major_id)
-- ----------------------------------------------------------------------------
CREATE TABLE ranking.rankings (
    id                SERIAL        PRIMARY KEY,
    ranking_name      VARCHAR(100)  NOT NULL,      -- 排名名称（软科/校友会/QS/US News/泰晤士/ESI/教育部学科评估）
    ranking_type      VARCHAR(30)   NOT NULL,      -- 排名类型（综合排名/学科排名/专业排名）
    ranking_year      INTEGER       NOT NULL,      -- 排名年份
    school_id         VARCHAR(10)   NOT NULL,      -- 院校ID（参照 base.schools.code_edu）
    major_id          VARCHAR(20),                 -- 专业/学科ID（学科排名时用，综合排名时为NULL）
    rank              INTEGER,                     -- 具体排名
    rank_total        INTEGER,                     -- 参评总数
    score             NUMERIC(8,2),                -- 总分/评分
    rank_change       VARCHAR(10),                 -- 较上年变化（+5/-3/NEW/-）
    tier              VARCHAR(10),                 -- 档次（学科评估用：A+/A/A-/B+/…）
    level_tag         VARCHAR(50),                 -- 等级标签（"世界一流"/"中国顶尖"/"区域一流"/…）
    data_source       VARCHAR(500),                -- 来源URL/出版物
    created_at        TIMESTAMP     DEFAULT NOW(),
    updated_at        TIMESTAMP     DEFAULT NOW(),
    UNIQUE (ranking_name, ranking_year, school_id, major_id)
);

-- ============================================================================
-- 8. 用户内容层 (user_content) — 评价、论坛帖、口碑指数
-- ============================================================================

-- ----------------------------------------------------------------------------
-- user_content.user_reviews — 用户评价表（短评类）
-- 数据来源：知乎/小红书/贴吧/豆瓣/抖音/B站/掌上高考等平台的公开评价
-- 去重键：(platform, platform_url)
-- ----------------------------------------------------------------------------
CREATE TABLE user_content.user_reviews (
    id                BIGSERIAL     PRIMARY KEY,
    school_id         VARCHAR(10),                 -- 院校ID（参照 base.schools.code_edu）
    major_id          VARCHAR(20),                 -- 专业ID（可为NULL，表示学校整体评价）
    platform          VARCHAR(30)   NOT NULL,      -- 平台来源（知乎/小红书/贴吧/豆瓣/抖音/B站/掌上高考/…）
    platform_url      VARCHAR(1000) NOT NULL,      -- 原文链接
    author_id         VARCHAR(64),                 -- 作者标识（脱敏，MD5）
    author_type       VARCHAR(20),                 -- 作者身份（在校生/毕业生/家长/教师/其他）
    content_text      TEXT,                        -- 评价内容
    content_length    INTEGER,                     -- 内容长度
    sentiment         VARCHAR(10),                 -- 情感倾向（positive/negative/neutral）
    sentiment_score   NUMERIC(4,2),                -- 情感得分（-1.0 ~ 1.0）
    tags              JSONB,                       -- 标签（"宿舍差"/"就业好"/"学习氛围"/…）
    like_count        INTEGER       DEFAULT 0,     -- 点赞数
    reply_count       INTEGER       DEFAULT 0,     -- 回复数
    publish_time      TIMESTAMP,                   -- 发布时间
    crawl_time        TIMESTAMP     DEFAULT NOW(), -- 采集时间
    is_useful         BOOLEAN       DEFAULT FALSE, -- 是否对志愿填报有参考价值（AI判断）
    data_source       VARCHAR(100),                -- 数据来源平台
    created_at        TIMESTAMP     DEFAULT NOW(),
    updated_at        TIMESTAMP     DEFAULT NOW(),
    UNIQUE (platform, platform_url)
);

-- ----------------------------------------------------------------------------
-- user_content.forum_posts — 论坛长帖/文章表
-- 数据来源：知乎长文、B站专栏、贴吧精华帖等
-- ----------------------------------------------------------------------------
CREATE TABLE user_content.forum_posts (
    id                BIGSERIAL     PRIMARY KEY,
    platform          VARCHAR(30)   NOT NULL,      -- 平台来源（知乎/B站/贴吧/…）
    thread_id         VARCHAR(100),                -- 帖子/话题ID
    title             VARCHAR(500),                -- 帖子标题
    content_text      TEXT,                        -- 正文内容
    school_id         VARCHAR(10),                 -- 关联院校（参照 base.schools.code_edu）
    major_id          VARCHAR(20),                 -- 关联专业
    platform_url      VARCHAR(1000),               -- 原文URL
    author_id         VARCHAR(64),                 -- 作者标识（脱敏，MD5）
    view_count        INTEGER       DEFAULT 0,     -- 阅读量
    like_count        INTEGER       DEFAULT 0,     -- 点赞数
    reply_count       INTEGER       DEFAULT 0,     -- 回复数
    favorite_count    INTEGER       DEFAULT 0,     -- 收藏数
    publish_time      TIMESTAMP,                   -- 发布时间
    crawl_time        TIMESTAMP     DEFAULT NOW(), -- 采集时间
    quality_score     INTEGER       DEFAULT 5,     -- 内容质量分（1-10，AI评估）
    summary           TEXT,                        -- AI摘要
    data_source       VARCHAR(100),                -- 数据来源
    created_at        TIMESTAMP     DEFAULT NOW(),
    updated_at        TIMESTAMP     DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- user_content.reputation_score — 口碑差异指数表 (README.md 新增)
-- 目标：每个院校 × 专业的"口碑综合得分"，
--       矛盾数据不掩盖，正面/负面都展示给用户判断
-- 去重键：(school_id, major_id, year)
-- ----------------------------------------------------------------------------
CREATE TABLE user_content.reputation_score (
    id                  SERIAL        PRIMARY KEY,
    school_id           VARCHAR(10)   NOT NULL,      -- 院校ID（参照 base.schools.code_edu）
    major_id            VARCHAR(20)   NOT NULL,      -- 专业ID
    year                INTEGER       NOT NULL DEFAULT 2026, -- 统计年份
    -- 综合数据
    total_mentions      INTEGER       DEFAULT 0,     -- 总提及数（所有平台）
    positive_count      INTEGER       DEFAULT 0,     -- 正面评价数
    negative_count      INTEGER       DEFAULT 0,     -- 负面评价数
    neutral_count       INTEGER       DEFAULT 0,     -- 中性评价数
    sentiment_score     NUMERIC(4,2),                -- 情感综合分（-1 ~ 1）
    -- 平台明细
    platform_breakdown  JSONB,                       -- 各平台的统计明细
    -- 高频关键词
    positive_keywords   TEXT[],                      -- 高频正面词
    negative_keywords   TEXT[],                      -- 高频负面词
    -- 可信度
    confidence          VARCHAR(10)   DEFAULT 'low', -- 可信度（high/medium/low）
    last_updated        TIMESTAMP     DEFAULT NOW(), -- 最后更新计算时间
    created_at          TIMESTAMP     DEFAULT NOW(),
    updated_at          TIMESTAMP     DEFAULT NOW(),
    UNIQUE (school_id, major_id, year)
);

-- ============================================================================
-- 9. 元数据层 (meta) — 采集任务、变更日志、附件
-- ============================================================================

-- ----------------------------------------------------------------------------
-- meta.crawl_tasks — 采集任务跟踪表
-- 用途：跟踪每一个数据采集任务的执行状态和计划
-- ----------------------------------------------------------------------------
CREATE TABLE meta.crawl_tasks (
    id                SERIAL        PRIMARY KEY,
    task_name         VARCHAR(200)  NOT NULL,      -- 任务名称
    target_url        VARCHAR(1000),               -- 目标URL/网站
    data_type         VARCHAR(50)   NOT NULL,      -- 数据类型（school/admission/policy/employment/ranking/ugc）
    crawl_strategy    VARCHAR(50),                 -- 采集策略（api/scrapy/selenium/playwright）
    frequency         VARCHAR(20)   DEFAULT 'once',-- 执行频率（once/daily/weekly/monthly/yearly）
    last_run_at       TIMESTAMP,                   -- 上次执行时间
    last_status       VARCHAR(20)   DEFAULT 'pending', -- 上次状态（success/failed/partial/pending）
    error_log         TEXT,                        -- 错误日志
    next_run_at       TIMESTAMP,                   -- 下次执行时间
    enabled           BOOLEAN       DEFAULT TRUE,  -- 是否启用
    created_at        TIMESTAMP     DEFAULT NOW(),
    updated_at        TIMESTAMP     DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- meta.data_change_log — 数据变更日志表
-- 用途：记录所有数据变更，支持审计追溯
-- ----------------------------------------------------------------------------
CREATE TABLE meta.data_change_log (
    id                BIGSERIAL     PRIMARY KEY,
    table_name        VARCHAR(100)  NOT NULL,      -- 变更表名
    row_id            VARCHAR(100)  NOT NULL,      -- 变更行ID
    change_type       VARCHAR(20)   NOT NULL,      -- 变更类型（insert/update/delete）
    old_values        JSONB,                       -- 旧值（JSON）
    new_values        JSONB,                       -- 新值（JSON）
    changed_by        VARCHAR(50)   DEFAULT 'system', -- 变更人（system/manual/用户名）
    change_reason     TEXT,                        -- 变更原因
    created_at        TIMESTAMP     DEFAULT NOW(),
    updated_at        TIMESTAMP     DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- meta.file_attachments — 文件附件表
-- 用途：管理PDF报告、院校图片、政策附件等文件的元数据
-- 去重：file_hash (SHA256)
-- ----------------------------------------------------------------------------
CREATE TABLE meta.file_attachments (
    id                SERIAL        PRIMARY KEY,
    file_type         VARCHAR(50)   NOT NULL,      -- 文件类型（pdf_report/school_logo/campus_photo/policy_attachment）
    source_table      VARCHAR(100),                -- 关联表名
    source_row_id     VARCHAR(50),                 -- 关联行ID
    original_filename VARCHAR(500),                -- 原始文件名
    stored_filename   VARCHAR(500),                -- 存储文件名
    file_size_bytes   BIGINT,                      -- 文件大小（字节）
    file_hash         VARCHAR(64),                 -- 文件SHA256哈希（用于去重）
    storage_path      VARCHAR(1000),               -- 本地文件路径或对象存储路径
    url               VARCHAR(1000),               -- 原始URL
    mime_type         VARCHAR(100),                -- MIME类型
    created_at        TIMESTAMP     DEFAULT NOW(),
    updated_at        TIMESTAMP     DEFAULT NOW()
);

-- ============================================================================
-- 10. 监控层 (monitor) — 网站巡检
-- ============================================================================

-- ----------------------------------------------------------------------------
-- monitor.site_check_log — 网站巡检日志表（简单版本）
-- 用途：记录对目标网站的定期巡检结果，监测改版/宕机/链接失效
-- ----------------------------------------------------------------------------
CREATE TABLE monitor.site_check_log (
    id                BIGSERIAL     PRIMARY KEY,
    site_name         VARCHAR(100)  NOT NULL,      -- 站点名称（如"陕西教育考试院"）
    site_url          VARCHAR(500)  NOT NULL,      -- 巡检URL
    data_type         VARCHAR(50),                 -- 相关数据类型（school/admission/policy/…）
    check_time        TIMESTAMP     DEFAULT NOW(), -- 巡检时间
    status            VARCHAR(20)   NOT NULL,      -- 状态（up/down/timeout/redirect/changed）
    response_time_ms  INTEGER,                     -- 响应时间（毫秒）
    http_status       INTEGER,                     -- HTTP状态码
    error_message     TEXT,                        -- 错误信息
    content_changed   BOOLEAN       DEFAULT FALSE, -- 内容结构是否发生变化
    created_at        TIMESTAMP     DEFAULT NOW(),
    updated_at        TIMESTAMP     DEFAULT NOW()
);

-- ============================================================================
-- 11. 索引
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 11.1 院校表索引
-- ----------------------------------------------------------------------------
CREATE INDEX idx_schools_province   ON base.schools (province);
CREATE INDEX idx_schools_level      ON base.schools (level);
CREATE INDEX idx_schools_category   ON base.schools (category);
CREATE INDEX idx_schools_is_211     ON base.schools (is_211) WHERE is_211 = TRUE;
CREATE INDEX idx_schools_is_985     ON base.schools (is_985) WHERE is_985 = TRUE;
CREATE INDEX idx_schools_double_first ON base.schools (is_double_first_class) WHERE is_double_first_class = TRUE;
-- 模糊搜索：院校名称
CREATE INDEX idx_schools_name_trgm  ON base.schools USING gin (name gin_trgm_ops);

-- ----------------------------------------------------------------------------
-- 11.2 专业目录索引
-- ----------------------------------------------------------------------------
CREATE INDEX idx_major_categories_parent ON base.major_categories (parent_id);
CREATE INDEX idx_major_categories_code   ON base.major_categories (category_code);

CREATE INDEX idx_majors_category    ON base.majors (category_id);
CREATE INDEX idx_majors_level       ON base.majors (level);
CREATE INDEX idx_majors_version     ON base.majors (version_year);
CREATE INDEX idx_majors_is_special  ON base.majors (is_special) WHERE is_special = TRUE;
-- 模糊搜索：专业名称
CREATE INDEX idx_majors_name_trgm   ON base.majors USING gin (name gin_trgm_ops);

-- ----------------------------------------------------------------------------
-- 11.3 录取数据索引（在分区父表上创建，自动继承到各分区）
-- ----------------------------------------------------------------------------
-- 核心查询：按院校+年份查录取数据
CREATE INDEX idx_admission_school_year ON admission.admission_data (school_id, year);
-- 核心查询：按专业+年份查录取数据
CREATE INDEX idx_admission_major_year  ON admission.admission_data (major_id, year)
    WHERE major_id IS NOT NULL;
-- 核心查询：按省份+批次+考生类别筛选
CREATE INDEX idx_admission_province_batch ON admission.admission_data (province, batch, student_category);
-- 分值区间查询：按分数范围筛选
CREATE INDEX idx_admission_score_rank ON admission.admission_data (year, province, student_category, admit_score_min);
-- 最常用场景：按省份+年份+考生类别+批次+位次范围查询
CREATE INDEX idx_admission_search ON admission.admission_data
    (province, year, student_category, batch, admit_rank_min);
-- 去重查询辅助
CREATE INDEX idx_admission_dedup ON admission.admission_data
    (school_id, major_id, province, year, batch, student_category);

-- ----------------------------------------------------------------------------
-- 11.4 省控线索引
-- ----------------------------------------------------------------------------
CREATE INDEX idx_pcl_province_year ON admission.province_score_lines (province, year);
CREATE INDEX idx_pcl_search        ON admission.province_score_lines (province, year, batch, student_category);

-- ----------------------------------------------------------------------------
-- 11.5 一分一段表索引
-- ----------------------------------------------------------------------------
CREATE INDEX idx_srs_province_year  ON admission.score_rank_segments (province, year, student_category);
CREATE INDEX idx_srs_score_lookup  ON admission.score_rank_segments (province, year, student_category, score);

-- ----------------------------------------------------------------------------
-- 11.6 政策表索引
-- ----------------------------------------------------------------------------
CREATE INDEX idx_policies_province_year ON policy.policies (province, year);
CREATE INDEX idx_policies_doc_type      ON policy.policies (document_type);
CREATE INDEX idx_policies_tags          ON policy.policies USING gin (tags);

-- ----------------------------------------------------------------------------
-- 11.7 就业数据索引
-- ----------------------------------------------------------------------------
CREATE INDEX idx_emp_stats_school    ON employment.employment_stats (school_id, year);
CREATE INDEX idx_emp_stats_major     ON employment.employment_stats (major_id, year);
CREATE INDEX idx_emp_stats_province  ON employment.employment_stats (province, year);

-- regional_job_stats
CREATE INDEX idx_regional_job_city    ON employment.regional_job_stats (city);
CREATE INDEX idx_regional_job_major   ON employment.regional_job_stats (major_id);
CREATE INDEX idx_regional_job_search  ON employment.regional_job_stats (city, major_id, year);
CREATE INDEX idx_regional_job_platform ON employment.regional_job_stats (platform, year, month);

-- employment_reports
CREATE INDEX idx_emp_reports_school   ON employment.employment_reports (school_id, year);

-- ----------------------------------------------------------------------------
-- 11.8 排名数据索引
-- ----------------------------------------------------------------------------
CREATE INDEX idx_rankings_school     ON ranking.rankings (school_id, ranking_year);
CREATE INDEX idx_rankings_major      ON ranking.rankings (major_id, ranking_year)
    WHERE major_id IS NOT NULL;
CREATE INDEX idx_rankings_name       ON ranking.rankings (ranking_name);
CREATE INDEX idx_rankings_name_year  ON ranking.rankings (ranking_name, ranking_year);

-- ----------------------------------------------------------------------------
-- 11.9 用户内容索引
-- ----------------------------------------------------------------------------
-- user_reviews
CREATE INDEX idx_reviews_school      ON user_content.user_reviews (school_id);
CREATE INDEX idx_reviews_major       ON user_content.user_reviews (major_id);
CREATE INDEX idx_reviews_platform    ON user_content.user_reviews (platform);
CREATE INDEX idx_reviews_sentiment   ON user_content.user_reviews (sentiment);
CREATE INDEX idx_reviews_publish_time ON user_content.user_reviews (publish_time DESC);
CREATE INDEX idx_reviews_is_useful   ON user_content.user_reviews (is_useful) WHERE is_useful = TRUE;
-- 全文搜索：评价内容
CREATE INDEX idx_reviews_content_trgm ON user_content.user_reviews USING gin (content_text gin_trgm_ops);

-- forum_posts
CREATE INDEX idx_posts_school        ON user_content.forum_posts (school_id);
CREATE INDEX idx_posts_major         ON user_content.forum_posts (major_id);
CREATE INDEX idx_posts_platform      ON user_content.forum_posts (platform);
CREATE INDEX idx_posts_quality       ON user_content.forum_posts (quality_score DESC);
CREATE INDEX idx_posts_publish_time  ON user_content.forum_posts (publish_time DESC);

-- reputation_score
CREATE INDEX idx_rep_score_school    ON user_content.reputation_score (school_id, year);
CREATE INDEX idx_rep_score_major     ON user_content.reputation_score (major_id, year);
CREATE INDEX idx_rep_score_confidence ON user_content.reputation_score (confidence);

-- ----------------------------------------------------------------------------
-- 11.10 元数据索引
-- ----------------------------------------------------------------------------
-- crawl_tasks
CREATE INDEX idx_crawl_tasks_type     ON meta.crawl_tasks (data_type);
CREATE INDEX idx_crawl_tasks_status   ON meta.crawl_tasks (last_status);
CREATE INDEX idx_crawl_tasks_enabled  ON meta.crawl_tasks (enabled) WHERE enabled = TRUE;
CREATE INDEX idx_crawl_tasks_next_run ON meta.crawl_tasks (next_run_at) WHERE enabled = TRUE;

-- data_change_log
CREATE INDEX idx_change_log_table     ON meta.data_change_log (table_name);
CREATE INDEX idx_change_log_type      ON meta.data_change_log (change_type);
CREATE INDEX idx_change_log_time      ON meta.data_change_log (created_at DESC);

-- file_attachments
CREATE INDEX idx_files_type           ON meta.file_attachments (file_type);
CREATE INDEX idx_files_source         ON meta.file_attachments (source_table, source_row_id);
CREATE INDEX idx_files_hash           ON meta.file_attachments (file_hash);

-- ----------------------------------------------------------------------------
-- 11.11 监控索引
-- ----------------------------------------------------------------------------
CREATE INDEX idx_site_check_site      ON monitor.site_check_log (site_url, check_time DESC);
CREATE INDEX idx_site_check_status    ON monitor.site_check_log (status);
CREATE INDEX idx_site_check_time      ON monitor.site_check_log (check_time DESC);
CREATE INDEX idx_site_check_datatype  ON monitor.site_check_log (data_type);

-- ============================================================================
-- 12. 表注释补充
-- ============================================================================
COMMENT ON TABLE base.schools                      IS '院校基础信息表 — 教育部全国高等学校名单 + 阳光高考';
COMMENT ON TABLE base.major_categories             IS '学科门类表 — 支持多级分类（门类→专业类→专业）';
COMMENT ON TABLE base.majors                       IS '专业目录表 — 教育部本科/专科专业目录，按年版本化';
COMMENT ON TABLE admission.admission_data          IS '历年录取数据（分区表）— 各省考试院投档线数据';
COMMENT ON TABLE admission.province_score_lines    IS '省控线表 — 各省高考批次分数线';
COMMENT ON TABLE admission.score_rank_segments     IS '一分一段表 — 各省高考成绩分段统计';
COMMENT ON TABLE policy.policies                   IS '招生政策表 — 各省/教育部招生工作规定';
COMMENT ON TABLE employment.employment_stats       IS '就业统计数据 — 院校/专业级别的就业率、薪资';
COMMENT ON TABLE employment.regional_job_stats     IS '地域招聘×专业关联 — 各城市各专业岗位数/薪资';
COMMENT ON TABLE employment.employment_reports     IS '就业质量报告 — 各高校年度就业质量报告元数据';
COMMENT ON TABLE ranking.rankings                  IS '排名数据 — 软科/校友会/QS/学科评估等';
COMMENT ON TABLE user_content.user_reviews         IS '用户评价（短评类）— 知乎/小红书/B站/贴吧等';
COMMENT ON TABLE user_content.forum_posts          IS '论坛长帖/文章 — 知乎长文、B站专栏等深度内容';
COMMENT ON TABLE user_content.reputation_score     IS '口碑差异指数 — 院校×专业综合口碑得分';
COMMENT ON TABLE meta.crawl_tasks                  IS '采集任务跟踪 — 爬虫任务的执行状态和计划';
COMMENT ON TABLE meta.data_change_log              IS '数据变更日志 — 所有数据修改的审计追溯';
COMMENT ON TABLE meta.file_attachments             IS '文件附件 — PDF报告、图片等文件元数据管理';
COMMENT ON TABLE monitor.site_check_log            IS '网站巡检日志 — 目标网站可用性和改版监测';

-- ============================================================================
-- 完成
-- ============================================================================
-- 表统计：
--   base:             3 张（schools, major_categories, majors）
--   admission:        3 张（admission_data 分区表 + province_score_lines + score_rank_segments）
--                     4 个分区（admission_2022, admission_2023, admission_2024, admission_2025）
--   policy:           1 张（policies）
--   employment:       3 张（employment_stats, regional_job_stats, employment_reports）
--   ranking:          1 张（rankings）
--   user_content:     3 张（user_reviews, forum_posts, reputation_score）
--   meta:             3 张（crawl_tasks, data_change_log, file_attachments）
--   monitor:          1 张（site_check_log）
--   ─────────────────────────────────────────────
--   合计：            18 张业务表 + 4 个分区 = 22 个 CREATE TABLE 语句
-- ============================================================================
