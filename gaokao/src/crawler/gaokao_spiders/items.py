"""
gaokao_spiders — Scrapy Items 定义

所有数据采集 Item 的统一定义，与 base.schools 等数据库表字段严格对齐。
"""

import scrapy


class SchoolItem(scrapy.Item):
    """院校信息 Item，字段与 base.schools 表对齐"""

    # === 核心标识 ===
    code_edu = scrapy.Field()              # 教育部院校代码（5位数字字符串，主键）
    name = scrapy.Field()                  # 院校全称

    # === 基本信息 ===
    name_aliases = scrapy.Field()          # 曾用名/别名（JSON数组）
    name_en = scrapy.Field()               # 英文名称
    code_gaokao = scrapy.Field()           # 高考院校代码（JSON按省份）
    code_yb = scrapy.Field()               # 研招网代码
    level = scrapy.Field()                 # 办学层次（本科/专科/职业本科）
    type = scrapy.Field()                  # 办学类型
    category = scrapy.Field()              # 院校类别
    is_211 = scrapy.Field()                # 是否211
    is_985 = scrapy.Field()                # 是否985
    is_double_first_class = scrapy.Field() # 是否双一流
    double_first_class_round = scrapy.Field()  # 双一流批次
    admin_department = scrapy.Field()      # 主管部门

    # === 地理位置 ===
    province = scrapy.Field()              # 所在省份
    city = scrapy.Field()                  # 所在城市
    district = scrapy.Field()              # 所在区县
    address = scrapy.Field()               # 详细地址
    postal_code = scrapy.Field()           # 邮政编码

    # === 联系方式 ===
    website = scrapy.Field()               # 官网URL
    admission_office_phone = scrapy.Field()  # 招生办电话
    admission_office_website = scrapy.Field()  # 招生网URL
    email = scrapy.Field()                 # 招生邮箱

    # === 媒体资源 ===
    logo_url = scrapy.Field()              # 校徽URL
    thumbnail_url = scrapy.Field()         # 校门图片URL

    # === 院校概况 ===
    established_year = scrapy.Field()      # 建校年份
    history = scrapy.Field()               # 校史简介
    area_acre = scrapy.Field()             # 占地面积（亩）
    student_undergrad = scrapy.Field()     # 本科生人数
    student_postgrad = scrapy.Field()      # 研究生人数
    student_total = scrapy.Field()         # 在校生总数
    faculty_count = scrapy.Field()         # 教职工总数
    faculty_professor = scrapy.Field()     # 教授人数
    library_volume = scrapy.Field()        # 图书馆藏书量

    # === 校区信息 ===
    campus_count = scrapy.Field()          # 校区数量
    campus_info = scrapy.Field()           # 校区信息（JSON）

    # === 学术实力 ===
    academician_count = scrapy.Field()     # 两院院士人数
    doctoral_programs = scrapy.Field()     # 博士点数量
    master_programs = scrapy.Field()       # 硕士点数量
    key_labs = scrapy.Field()              # 国家重点实验室（JSON数组）
    features = scrapy.Field()              # 办学特色标签（JSON数组）

    # === 费用信息 ===
    scholarship_info = scrapy.Field()      # 奖助学金信息
    tuition_range = scrapy.Field()         # 学费范围（JSON）
    accommodation = scrapy.Field()         # 住宿条件描述
    accommodation_fee = scrapy.Field()     # 住宿费范围

    # === 元数据 ===
    data_source = scrapy.Field()           # 数据来源标记
    data_version = scrapy.Field()          # 数据版本/年份
    created_at = scrapy.Field()            # 记录创建时间
    updated_at = scrapy.Field()            # 记录更新时间


class MajorItem(scrapy.Item):
    """专业信息 Item"""
    major_id = scrapy.Field()
    name = scrapy.Field()
    name_full = scrapy.Field()
    category_id = scrapy.Field()
    subject_group = scrapy.Field()
    subject_group_3p3 = scrapy.Field()
    level = scrapy.Field()
    study_years = scrapy.Field()
    degree = scrapy.Field()
    description = scrapy.Field()
    main_courses = scrapy.Field()
    typical_schools = scrapy.Field()
    employment_rate = scrapy.Field()
    employment_direction = scrapy.Field()
    salary_avg = scrapy.Field()
    is_special = scrapy.Field()
    special_label = scrapy.Field()
    version_year = scrapy.Field()
    data_source = scrapy.Field()
    created_at = scrapy.Field()
    updated_at = scrapy.Field()
