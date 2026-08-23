"""
基于 KOS（知识组织体系）的知识抽取核心算法。

设计思路：以"KOS 词表驱动 + 统计算法（TF-IDF）+ 规则匹配"为核心，不依赖 LLM。
- 内置多领域 KOS 词表（范畴分类 / 主题概念 / 领域术语）
- 滑动窗口最长匹配进行术语识别
- TF-IDF 计算术语重要度
- 按目标分类体系进行范畴归类
- 构建概念层级（属于范畴/属于概念）与关联（相关）关系
"""
import math
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

# ============================================================
# 内置 KOS 词表（知识组织体系）
# 结构：范畴分类 -> 主题概念 -> 领域术语
# 覆盖农业、信息技术、医药卫生、经济管理、教育文化等领域
# 对应文档中的目标分类体系：PRES/CCT/CASDD/CNE/STKOS/NSTL
# ============================================================

KOS_VOCABULARY: Dict[str, Dict[str, List[str]]] = {
    # 农业科学（对应 CASDD）
    "农业科学": {
        "农作物": ["水稻", "小麦", "玉米", "大豆", "棉花", "茶叶", "甘蔗", "油菜", "高粱", "谷子",
                  "马铃薯", "甘薯", "花生", "芝麻", "烟草", "蚕桑", "亚麻", "甜菜", "向日葵", "柑橘",
                  "苹果", "葡萄", "梨", "桃", "香蕉", "橡胶", "咖啡", "可可", "杂粮", "青稞"],
        "畜禽养殖": ["生猪", "肉牛", "奶牛", "家禽", "绵羊", "山羊", "鸡", "鸭", "鹅", "饲料",
                    "肉鸡", "蛋鸡", "蛋鸭", "种猪", "仔猪", "母猪", "肉羊", "兔子", "鸽子", "鹌鹑",
                    "水产养殖", "鱼", "虾", "蟹", "贝", "海参", "鲍鱼", "蚕", "蜂", "蚕茧"],
        "病虫害防治": ["稻瘟病", "纹枯病", "蚜虫", "螟虫", "飞虱", "病害", "虫害", "农药", "防治", "检疫",
                      "白粉病", "锈病", "赤霉病", "黑穗病", "蝗虫", "红蜘蛛", "线虫", "粘虫", "除草剂", "杀虫剂",
                      "杀菌剂", "生物防治", "综合防治", "测报", "疫区", "抗药性", "天敌", "寄生蜂", "性诱剂", "熏蒸"],
        "土壤肥料": ["土壤", "肥料", "氮肥", "磷肥", "钾肥", "有机肥", "壤土", "盐碱地", "改良",
                    "化肥", "复合肥", "微肥", "菌肥", "腐殖酸", "测土配方", "基肥", "追肥", "叶面肥", "中耕", "免耕",
                    "砂土", "黏土", "黑土", "黄土", "红壤", "沙化", "侵蚀", "酸化", "板结", "地力"],
        "农业技术": ["育种", "栽培", "灌溉", "温室", "农机", "采收", "嫁接", "轮作", "杂交",
                    "转基因", "分子育种", "精准农业", "智慧农业", "设施农业", "节水农业", "滴灌", "喷灌", "大棚", "地膜", "间作",
                    "套种", "连作", "休耕", "土壤消毒", "组培", "无性繁殖", "无土栽培", "有机农业", "生态农业", "观光农业"],
        "林业园艺": ["森林", "造林", "林木", "种苗", "苗圃", "绿化", "防护林", "公益林", "木材", "竹林",
                    "园艺", "花卉", "盆景", "草坪", "苗木", "果树", "修剪", "整形", "扦插", "压条",
                    "橡胶林", "油茶林", "油橄榄", "核桃", "板栗", "枣", "柿", "猕猴桃", "蓝莓", "草莓"],
        "农产品加工": ["粮食加工", "食品加工", "贮藏", "保鲜", "冷链", "烘干", "碾米", "磨面", "榨油", "酿造",
                      "罐头", "脱水", "腌制", "发酵", "乳制品", "肉制品", "豆制品", "副产物", "深加工", "品牌化",
                      "分级", "包装", "追溯", "质检", "绿色食品", "有机食品", "地理标志", "农产品流通", "仓储", "配送"],
        "农业资源与环境": ["耕地", "草地", "湿地", "水域", "水资源", "土地整治", "高标准农田", "退耕还林", "退牧还草", "水土保持",
                          "面源污染", "农膜回收", "秸秆", "粪污", "资源化", "碳汇", "碳中和", "气象", "干旱", "洪涝",
                          "低温冻害", "冰雹", "台风", "沙漠化", "石漠化", "生物多样性", "天敌资源", "种质资源", "基因库", "保种"],
    },
    # 信息技术（对应 STKOS）
    "信息技术": {
        "人工智能": ["人工智能", "机器学习", "深度学习", "神经网络", "自然语言处理", "计算机视觉",
                    "知识图谱", "大模型", "算法", "训练", "推理", "向量数据库", "嵌入",
                    "卷积神经网络", "循环神经网络", "Transformer", "注意力机制", "预训练", "微调", "强化学习", "监督学习", "无监督学习", "半监督学习",
                    "小样本学习", "零样本学习", "多模态", "语音识别", "语音合成", "OCR", "人脸识别", "目标检测", "语义分割", "智能体"],
        "软件开发": ["软件", "程序", "代码", "框架", "接口", "数据库", "服务器", "前端", "后端",
                    "微服务", "容器", "部署", "调试", "编译",
                    "敏捷开发", "DevOps", "CI/CD", "版本控制", "Git", "单元测试", "集成测试", "重构", "代码审查", "设计模式",
                    "面向对象", "函数式编程", "低代码", "无代码", "SDK", "API", "文档", "日志", "监控", "告警"],
        "网络通信": ["网络", "互联网", "协议", "带宽", "路由器", "云计算", "边缘计算", "5G",
                    "物联网", "区块链", "网络安全", "加密",
                    "TCP/IP", "HTTP", "DNS", "CDN", "负载均衡", "交换机", "防火墙", "VPN", "IPv6", "WiFi",
                    "蓝牙", "ZigBee", "LoRa", "卫星通信", "量子通信", "SDN", "NFV", "数据中心", "机房", "带宽"],
        "数据科学": ["数据", "数据挖掘", "数据分析", "大数据", "数据仓库", "可视化", "统计",
                    "特征工程", "建模", "指标",
                    "Hadoop", "Spark", "Flink", "Kafka", "Hive", "HBase", "ClickHouse", "ETL", "OLAP", "OLTP",
                    "BI", "报表", "Dashboard", "数据湖", "数据中台", "数据治理", "元数据", "主数据", "数据血缘", "数据质量"],
        "信息安全": ["安全", "渗透测试", "漏洞", "攻击", "防御", "入侵检测", "防火墙", "WAF", "身份认证", "授权",
                    "审计", "日志审计", "加密算法", "对称加密", "非对称加密", "哈希", "数字签名", "证书", "PKI", "零信任",
                    "数据脱敏", "数据加密", "隐私计算", "联邦学习", "可信执行环境", "APT", "勒索病毒", "木马", "钓鱼", "应急响应"],
        "软件工程与架构": ["需求分析", "系统设计", "架构设计", "高可用", "高并发", "分布式", "集群", "容灾", "备份", "恢复",
                          "微服务架构", "服务网格", "消息队列", "缓存", "Redis", "分库分表", "读写分离", "限流", "熔断", "降级",
                          "领域驱动设计", "事件驱动", "CQRS", "六边形架构", "Serverless", "云原生", "Kubernetes", "Docker", "服务治理", "配置中心"],
        "硬件与系统": ["CPU", "GPU", "内存", "硬盘", "SSD", "主板", "服务器", "存储", "操作系统", "Linux",
                      "Windows", "Unix", "内核", "进程", "线程", "文件系统", "驱动程序", "BIOS", "固件", "嵌入式",
                      "单片机", "FPGA", "ASIC", "RISC-V", "ARM", "x86", "边缘设备", "传感器", "RFID", "二维码"],
    },
    # 医药卫生（对应 CNE）
    "医药卫生": {
        "疾病": ["糖尿病", "高血压", "冠心病", "肿瘤", "肺炎", "肝炎", "胃炎", "流感",
                "慢性病", "传染病", "症状", "诊断", "预后",
                "中风", "心肌梗死", "哮喘", "慢阻肺", "肾病", "甲状腺疾病", "贫血", "白血病", "淋巴瘤", "阿尔茨海默病",
                "帕金森", "抑郁症", "焦虑症", "精神分裂症", "过敏", "红斑狼疮", "类风湿性关节炎", "艾滋病", "结核病", "新冠病毒"],
        "药物": ["药物", "抗生素", "疫苗", "中药", "西药", "处方", "剂量", "疗效",
                "不良反应", "临床试验", "靶向药",
                "中成药", "饮片", "炮制", "君臣佐使", "辨证论治", "小分子药", "大分子药", "单抗", "双抗", "ADC",
                "免疫抑制剂", "激素", "维生素", "矿物质", "益生菌", "纳米药物", "缓释制剂", "控释制剂", "仿制药", "创新药"],
        "医疗技术": ["手术", "影像", "检验", "内窥镜", "放疗", "化疗", "免疫治疗",
                    "基因检测", "康复", "护理",
                    "CT", "MRI", "X光", "超声", "PET-CT", "病理", "病理切片", "免疫组化", "介入治疗", "微创手术",
                    "机器人手术", "达芬奇", "器官移植", "心脏搭桥", "支架", "起搏器", "透析", "输血", "氧疗", "镇痛"],
        "公共卫生": ["防疫", "疾控", "健康", "卫生", "流行病学", "筛查", "接种",
                    "隔离", "监测", "防控",
                    "健康教育", "健康促进", "职业病", "食品卫生", "环境卫生", "学校卫生", "职业健康", "妇幼保健", "老年保健", "慢病管理",
                    "突发公共卫生事件", "应急预案", "流行病学调查", "密切接触者", "溯源", "疫苗接种率", "群体免疫", "消杀", "医疗废物", "饮用水安全"],
        "中医药学": ["中医", "中药", "方剂", "针灸", "推拿", "拔罐", "刮痧", "艾灸", "望闻问切", "阴阳",
                    "五行", "经络", "穴位", "气血", "脏腑", "辨证", "八纲", "六经", "卫气营血", "三焦",
                    "伤寒论", "金匮要略", "黄帝内经", "本草纲目", "孙思邈", "李时珍", "张仲景", "华佗", "冬病夏治", "治未病"],
        "临床专科": ["内科", "外科", "妇产科", "儿科", "眼科", "耳鼻喉科", "口腔科", "皮肤科", "精神科", "神经内科",
                    "心血管内科", "呼吸内科", "消化内科", "肾内科", "内分泌科", "血液科", "骨科", "泌尿外科", "心胸外科", "神经外科",
                    "肿瘤科", "放射科", "核医学", "超声科", "麻醉科", "ICU", "急诊科", "康复科", "营养科", "感染科"],
        "医药产业": ["药企", "药品研发", "仿制药一致性评价", "新药审批", "NMPA", "FDA", "GMP", "GSP", "GLP", "GCP",
                    "药品集采", "医保", "DRG", "DIP", "两票制", "带量采购", "基本药物", "处方药", "非处方药", "保健品",
                    "原料药", "中间体", "生物药", "CRO", "CMO", "CDMO", "CXO", "医药电商", "互联网医院", "远程诊疗"],
    },
    # 经济管理（对应 CCT）
    "经济管理": {
        "宏观经济": ["经济", "GDP", "通胀", "通缩", "财政", "货币政策", "利率", "汇率",
                    "贸易", "投资", "消费", "出口", "进口",
                    "PMI", "CPI", "PPI", "失业率", "居民收入", "社零总额", "固定资产投资", "外汇储备", "M2", "社融",
                    "供给侧改革", "需求侧管理", "双循环", "内循环", "外循环", "逆周期调节", "跨周期调节", "财政赤字", "专项债", "国债"],
        "企业管理": ["企业", "管理", "战略", "运营", "营销", "供应链", "成本", "利润",
                    "品牌", "客户", "绩效", "组织",
                    "KPI", "OKR", "BSC", "HR", "招聘", "培训", "薪酬", "激励", "企业文化", "愿景",
                    "使命", "价值观", "治理结构", "董事会", "监事会", "股权激励", "合伙人", "并购", "重组", "破产"],
        "金融市场": ["股票", "债券", "基金", "期货", "银行", "保险", "证券", "风险",
                    "资产", "估值", "收益", "杠杆",
                    "ETF", "REITs", "可转债", "期权", "互换", "量化交易", "高频交易", "散户", "机构投资者", "北向资金",
                    "IPO", "注册制", "科创板", "创业板", "新三板", "北交所", "上证指数", "沪深300", "道琼斯", "纳斯达克"],
        "产业经济": ["产业", "产业链", "集群", "园区", "转型升级", "创新驱动", "新动能",
                    "高质量发展", "数字经济", "绿色经济",
                    "实体经济", "虚拟经济", "先进制造业", "现代服务业", "战略性新兴产业", "新能源", "新材料", "生物医药", "航空航天", "集成电路",
                    "专精特新", "小巨人", "独角兽", "隐形冠军", "头部企业", "龙头企业", "产业政策", "招商引资", "飞地经济", "对口支援"],
        "财政与税收": ["税收", "税率", "增值税", "企业所得税", "个人所得税", "消费税", "关税", "减税降费", "留抵退税", "税收优惠",
                      "财政支出", "转移支付", "一般性转移支付", "专项转移支付", "中央财政", "地方财政", "土地财政", "预算", "决算", "审计",
                      "政府债务", "隐性债务", "地方债", "城投债", "PPP", "政府购买服务", "预算绩效管理", "国库", "政府采购", "三公经费"],
        "国际贸易与投资": ["进出口", "关税", "原产地", "自贸区", "自贸港", "保税区", "出口加工区", "跨境电商", "外贸", "外资",
                          "对外投资", "一带一路", "RCEP", "CPTPP", "WTO", "世界银行", "IMF", "贸易顺差", "贸易逆差", "外汇管理",
                          "QDII", "QFII", "跨境人民币", "人民币国际化", "离岸市场", "在岸市场", "反倾销", "反补贴", "保障措施", "贸易摩擦"],
        "市场营销与品牌": ["市场调研", "消费者行为", "市场细分", "目标市场", "定位", "4P", "4C", "STP", "品牌建设", "品牌价值",
                          "广告", "公关", "促销", "渠道", "分销", "直营", "加盟", "连锁", "新零售", "直播电商",
                          "私域流量", "公域流量", "转化", "留存", "复购", "客单价", "GMV", "ROI", "用户画像", "精准营销"],
    },
    # 教育文化（对应 PRES）
    "教育文化": {
        "教育教学": ["教育", "教学", "课程", "课堂", "学生", "教师", "学校", "培训",
                    "考核", "素质教育", "职业教育", "高等教育",
                    "学前教育", "义务教育", "普通高中", "中职", "专科", "本科", "硕士", "博士", "博士后", "研究生院",
                    "新课标", "双减", "五育并举", "立德树人", "核心素养", "课程思政", "翻转课堂", "混合式教学", "MOOC", "在线教育",
                    "教学设计", "教案", "学案", "板书", "课件", "多媒体教学", "实验教学", "实习", "实训", "毕业设计"],
        "科学研究": ["科学", "技术", "研究", "实验", "创新", "专利", "成果", "学术",
                    "论文", "课题", "协作", "转化",
                    "基础研究", "应用研究", "试验发展", "R&D", "国家重点实验室", "国家实验室", "中科院", "工程院", "院士", "973计划",
                    "863计划", "重点研发计划", "自然科学基金", "社科基金", "科技进步奖", "技术发明奖", "科技成果转化", "产学研用", "孵化器", "众创空间"],
        "文化遗产": ["文化", "遗产", "文物", "非遗", "博物馆", "考古", "保护", "传承",
                    "文献", "古籍", "遗址",
                    "故宫", "长城", "兵马俑", "莫高窟", "颐和园", "天坛", "布达拉宫", "大运河", "丝绸之路", "世界遗产",
                    "物质文化遗产", "非物质文化遗产", "传承人", "传统工艺", "传统戏曲", "传统节日", "二十四节气", "民俗", "方言", "族谱"],
        "传播出版": ["出版", "媒体", "传播", "新闻", "期刊", "图书", "版权", "发行",
                    "数字出版", "融媒体",
                    "报纸", "杂志", "出版社", "印刷厂", "新华书店", "馆配", "馆配商", "编校", "装帧设计", "ISBN",
                    "ISSN", "DOI", "开放获取", "SCI", "SSCI", "CSSCI", "北大核心", "知网", "万方", "维普"],
        "艺术与文创": ["音乐", "舞蹈", "戏剧", "戏曲", "电影", "电视", "美术", "绘画", "书法", "雕塑",
                      "摄影", "建筑", "设计", "动漫", "游戏", "短视频", "网剧", "综艺", "纪录片", "舞台剧",
                      "文创产品", "IP开发", "衍生品", "文旅融合", "沉浸式体验", "数字艺术", "NFT", "元宇宙", "博物馆文创", "国家文化公园"],
        "体育与健康": ["体育", "竞技体育", "群众体育", "全民健身", "奥运会", "亚运会", "全运会", "世界杯", "足球", "篮球",
                      "排球", "乒乓球", "羽毛球", "游泳", "田径", "体操", "举重", "射击", "冰雪运动", "马拉松",
                      "健身", "瑜伽", "普拉提", "跑步", "骑行", "徒步", "登山", "滑雪", "冲浪", "健康管理",
                      "作息", "饮食", "营养", "减肥", "体检", "心理健康", "压力管理", "睡眠", "戒烟限酒", "健康生活方式"],
        "语言文学历史": ["语言学", "文字学", "音韵学", "训诂学", "现代汉语", "古代汉语", "汉字", "拼音", "成语", "谚语",
                        "诗歌", "散文", "小说", "戏剧文学", "文学批评", "比较文学", "古典文学", "现代文学", "当代文学", "外国文学",
                        "中国历史", "世界历史", "古代史", "近代史", "现代史", "当代史", "史学理论", "史料学", "历史地理", "考古学"],
    },
}

# 扁平化术语表：术语 -> (范畴, 概念)，便于快速查找
TERM_INDEX: Dict[str, Tuple[str, str]] = {}
for _cat, _concepts in KOS_VOCABULARY.items():
    for _concept, _terms in _concepts.items():
        for _term in _terms:
            TERM_INDEX[_term] = (_cat, _concept)

# 所有术语按长度倒序排列（最长匹配优先）
ALL_TERMS_SORTED: List[str] = sorted(TERM_INDEX.keys(), key=len, reverse=True)

# 实体识别类型 -> 对应的实体 type 标签
ENTITY_TYPE_MAP = {
    "高频术语": "高频术语",
    "主题概念": "主题概念",
    "范畴分类": "范畴分类",
    "组织机构": "组织机构",
    "专家学者": "专家学者",
    "学术期刊": "学术期刊",
}

# 内置组织机构 / 专家学者 / 学术期刊 样例词表（增强识别能力）
ORGANIZATIONS: List[str] = [
    # 国内科研院所
    "中国科学院", "中国农业科学院", "中国医学科学院", "中国社会科学院", "中国工程院",
    "国家自然科学基金委员会", "科技部", "农业农村部", "教育部", "国家卫生健康委员会",
    "国家发改委", "工信部", "商务部", "自然资源部", "生态环境部", "财政部",
    "中国林业科学研究院", "中国水产科学研究院", "中国地质科学院", "中国气象局", "中国地震局",
    "国家中医药管理局", "国家药品监督管理局", "国家知识产权局", "国家标准委", "中国科协",
    # 国内高校
    "清华大学", "北京大学", "浙江大学", "复旦大学", "上海交通大学", "南京大学",
    "中国科学技术大学", "武汉大学", "华中科技大学", "中山大学", "西安交通大学",
    "同济大学", "北京航空航天大学", "哈尔滨工业大学", "东南大学", "四川大学",
    "吉林大学", "山东大学", "南开大学", "北京师范大学", "天津大学",
    "中南大学", "厦门大学", "中国农业大学", "北京协和医学院", "华南理工大学",
    "大连理工大学", "西北工业大学", "华东师范大学", "中国人民大学",
    # 国际组织与机构
    "世界卫生组织", "联合国粮农组织", "联合国教科文组织", "世界银行", "国际货币基金组织",
    "世界贸易组织", "联合国", "经合组织", "亚太经合组织", "欧盟",
    # 企业与医疗机构
    "中国科学院大学", "国家图书馆", "中国国家博物馆", "故宫博物院", "国家博物馆",
]
EXPERTS: List[str] = [
    # 历史/当代知名科学家
    "袁隆平", "屠呦呦", "钟南山", "钱学森", "华罗庚", "李四光",
    "施一公", "张文宏", "高福", "陈薇",
    "邓稼先", "于敏", "钱三强", "竺可桢", "茅以升",
    "童第周", "侯德榜", "梁思成", "林徽因", "苏步青",
    "谷超豪", "王选", "黄昆", "周光召", "朱光亚",
    "潘建伟", "薛其坤", "颜宁", "丘成桐", "杨振宁",
    "李政道", "丁肇中", "李兰娟", "张伯礼", "黄旭华",
    "曾庆存", "刘永坦", "钱七虎", "王泽山", "侯云德",
    "屠守锷", "郭永怀", "王淦昌", "赵忠尧", "吴文俊",
]
JOURNALS: List[str] = [
    # 国际顶刊
    "Nature", "Science", "Cell", "The Lancet", "New England Journal of Medicine",
    "JAMA", "BMJ", "PNAS", "Nature Genetics", "Nature Medicine",
    "Cell Research", "IEEE Transactions on Pattern Analysis and Machine Intelligence",
    "Communications of the ACM", "The Journal of Finance", "Quarterly Journal of Economics",
    # 国内顶刊
    "中国科学", "科学通报", "中华医学杂志", "农业科学", "计算机学报",
    "经济研究", "中国社会科学", "管理世界", "软件学报", "电子学报",
    "自动化学报", "中文信息学报", "情报学报", "中国农业科学", "作物学报",
    "植物保护学报", "畜牧兽医学报", "中华内科杂志", "中华外科杂志", "中华肿瘤杂志",
    "药学学报", "中国中药杂志", "中草药", "教育研究", "心理学报",
    "文学评论", "历史研究", "哲学研究", "经济研究参考", "南开管理评论",
    "中国软科学", "科研管理", "研究与发展管理", "中国图书馆学报",
]


# ============================================================
# 文本预处理
# ============================================================

def preprocess(text: str) -> List[str]:
    """文本预处理：按标点切分为句子片段，便于后续共现统计。"""
    if not text:
        return []
    # 统一全角标点为半角，便于切分
    text = text.replace("\n", "。").replace("\r", "。")
    # 按句号/问号/感叹号/分号切分
    fragments = re.split(r"[。！？!?\.;；]+", text)
    # 过滤空白片段
    return [f.strip() for f in fragments if f.strip()]


# ============================================================
# 术语识别（滑动窗口 + 最长匹配）
# ============================================================

def extract_terms(text: str) -> List[Tuple[str, int, int]]:
    """
    从文本中识别 KOS 词表中的术语，返回 (术语, 起始位置, 结束位置) 列表。
    采用最长匹配优先策略，避免短术语覆盖长术语。
    """
    if not text:
        return []
    results: List[Tuple[str, int, int]] = []
    n = len(text)
    # 记录已匹配的字符位置，避免重叠
    occupied: List[bool] = [False] * n

    # 按术语长度倒序匹配
    for term in ALL_TERMS_SORTED:
        tlen = len(term)
        if tlen > n:
            continue
        start = 0
        while start <= n - tlen:
            # 跳过已被占用的位置
            if any(occupied[start:start + tlen]):
                start += 1
                continue
            if text[start:start + tlen] == term:
                results.append((term, start, start + tlen))
                for k in range(start, start + tlen):
                    occupied[k] = True
                start += tlen
            else:
                start += 1
    # 按位置排序
    results.sort(key=lambda x: x[1])
    return results


def extract_named_entities(text: str) -> Dict[str, List[Tuple[str, int, int]]]:
    """识别组织机构、专家学者、学术期刊等命名实体。"""
    found: Dict[str, List[Tuple[str, int, int]]] = {
        "组织机构": [],
        "专家学者": [],
        "学术期刊": [],
    }
    for name_list, etype in [(ORGANIZATIONS, "组织机构"), (EXPERTS, "专家学者"), (JOURNALS, "学术期刊")]:
        for name in sorted(name_list, key=len, reverse=True):
            start = 0
            while True:
                idx = text.find(name, start)
                if idx < 0:
                    break
                found[etype].append((name, idx, idx + len(name)))
                start = idx + len(name)
    return found


# ============================================================
# TF-IDF 统计
# ============================================================

def compute_tfidf(fragments: List[str], terms_in_doc: Dict[str, int]) -> Dict[str, float]:
    """
    计算文档内术语的 TF-IDF 得分。
    - TF: 术语在文档中的出现频次 / 文档总术语数
    - IDF: log(总片段数 / 包含该术语的片段数 + 1)
    """
    total_terms = sum(terms_in_doc.values()) or 1
    num_fragments = len(fragments) or 1

    # 统计每个术语出现在多少个片段中（DF）
    df: Counter = Counter()
    for frag in fragments:
        frag_terms: Set[str] = set()
        for term in ALL_TERMS_SORTED:
            if term in frag:
                frag_terms.add(term)
        for t in frag_terms:
            df[t] += 1

    tfidf: Dict[str, float] = {}
    for term, freq in terms_in_doc.items():
        tf = freq / total_terms
        idf = math.log((num_fragments + 1) / (df.get(term, 0) + 1)) + 1
        tfidf[term] = round(tf * idf, 4)
    return tfidf


# ============================================================
# 概念归类与关系构建
# ============================================================

def build_concept_entities(
    terms_in_doc: Dict[str, int],
    tfidf: Dict[str, float],
    term_count: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    根据识别出的术语，构建三类实体：高频术语、主题概念、范畴分类。
    返回：(高频术语实体列表, 主题概念实体列表, 范畴分类实体列表)
    """
    # 1. 高频术语实体（按 TF-IDF 排序，取前 N 个）
    sorted_terms = sorted(
        tfidf.items(), key=lambda x: x[1], reverse=True
    )[:term_count]
    term_entities: List[Dict[str, Any]] = []
    for term, score in sorted_terms:
        cat, concept = TERM_INDEX.get(term, ("未知", "未知"))
        term_entities.append({
            "name": term,
            "type": "高频术语",
            "properties": {
                "tfidfScore": score,
                "frequency": terms_in_doc.get(term, 0),
                "concept": concept,
                "category": cat,
            },
        })

    # 2. 主题概念实体（聚合术语所属概念，按概念内术语得分求和排序）
    concept_scores: Dict[str, float] = defaultdict(float)
    concept_to_cat: Dict[str, str] = {}
    concept_term_count: Dict[str, int] = defaultdict(int)
    for term, score in tfidf.items():
        cat, concept = TERM_INDEX.get(term, ("未知", "未知"))
        if concept == "未知":
            continue
        concept_scores[concept] += score
        concept_to_cat[concept] = cat
        concept_term_count[concept] += 1

    sorted_concepts = sorted(
        concept_scores.items(), key=lambda x: x[1], reverse=True
    )[:term_count]
    concept_entities: List[Dict[str, Any]] = []
    for concept, score in sorted_concepts:
        concept_entities.append({
            "name": concept,
            "type": "主题概念",
            "properties": {
                "score": round(score, 4),
                "termCount": concept_term_count[concept],
                "category": concept_to_cat[concept],
            },
        })

    # 3. 范畴分类实体（聚合概念所属范畴，按范畴内概念得分求和排序）
    category_scores: Dict[str, float] = defaultdict(float)
    category_concept_count: Dict[str, int] = defaultdict(int)
    for concept, score in concept_scores.items():
        cat = concept_to_cat.get(concept, "未知")
        category_scores[cat] += score
        category_concept_count[cat] += 1

    sorted_categories = sorted(
        category_scores.items(), key=lambda x: x[1], reverse=True
    )[:term_count]
    category_entities: List[Dict[str, Any]] = []
    for cat, score in sorted_categories:
        category_entities.append({
            "name": cat,
            "type": "范畴分类",
            "properties": {
                "score": round(score, 4),
                "conceptCount": category_concept_count[cat],
            },
        })

    return term_entities, concept_entities, category_entities


def build_relations(
    term_entities: List[Dict[str, Any]],
    concept_entities: List[Dict[str, Any]],
    category_entities: List[Dict[str, Any]],
    fragments: List[str],
    prefix: str = "",
) -> List[Dict[str, Any]]:
    """
    构建关系：
    - 术语 -> 属于概念 -> 主题概念实体
    - 概念 -> 属于范畴 -> 范畴分类实体
    - 术语 -> 相关（同片段共现） -> 术语
    前缀处理：范畴分类前缀拼接
    """
    relations: List[Dict[str, Any]] = []
    term_names = {e["name"] for e in term_entities}
    concept_names = {e["name"] for e in concept_entities}
    category_names = {e["name"] for e in category_entities}

    # 1. 术语 -属于概念-> 概念
    for te in term_entities:
        concept = te["properties"].get("concept")
        if concept and concept in concept_names:
            relations.append({
                "head": te["name"],
                "relation": "属于概念",
                "tail": concept,
                "properties": {"score": te["properties"].get("tfidfScore", 0)},
            })

    # 2. 概念 -属于范畴-> 范畴分类（应用前缀）
    for ce in concept_entities:
        cat = ce["properties"].get("category")
        if cat:
            target_cat = f"{prefix}{cat}" if prefix else cat
            if cat in category_names:
                relations.append({
                    "head": ce["name"],
                    "relation": "属于范畴",
                    "tail": target_cat,
                    "properties": {"score": ce["properties"].get("score", 0)},
                })

    # 3. 术语 -相关-> 术语（基于片段共现）
    co_occurrence: Counter = Counter()
    for frag in fragments:
        frag_terms = [t for t in term_names if t in frag]
        # 两两组合
        for i in range(len(frag_terms)):
            for j in range(i + 1, len(frag_terms)):
                pair = tuple(sorted([frag_terms[i], frag_terms[j]]))
                co_occurrence[pair] += 1
    # 取共现频次 >= 2 的关系
    for (t1, t2), count in co_occurrence.most_common(50):
        if count >= 2:
            relations.append({
                "head": t1,
                "relation": "相关",
                "tail": t2,
                "properties": {"coOccurrence": count},
            })

    return relations


# ============================================================
# 主抽取入口
# ============================================================

def extract(
    text: str,
    kos_config: Dict[str, Any],
    ontology: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    KOS 知识抽取主入口。

    :param text: 待抽取文本
    :param kos_config: KOS 抽取参数，含：
        - termCount: 高频术语数量（默认 10）
        - conceptCount: 高频概念数量（默认 10）
        - categoryCount: 范畴分类数量（默认 10）
        - scoreBasis: 分类得分依据（高频术语/语义关联）
        - weight: 分类体系权重（默认 1）
        - useWeight: 是否考虑权重（是/否）
        - targetSystems: 目标分类体系列表（PRES/CCT/CASDD/CNE/STKOS/NSTL）
        - multiDoc: 是否多文档（是/否）
        - categoryPrefix: 范畴分类前缀
        - returnWords: 是否返回词（是/否）
        - entityTypes: 实体识别类型列表
    :param ontology: 当前图谱模型的本体 Schema（可选，用于类型对齐）
    :return: {entities, relations, duration, writeCount}
    """
    # 参数解析（带默认值）
    term_count = int(kos_config.get("termCount", 10))
    concept_count = int(kos_config.get("conceptCount", 10))
    category_count = int(kos_config.get("categoryCount", 10))
    prefix = kos_config.get("categoryPrefix", "")
    entity_types = kos_config.get("entityTypes", ["高频术语", "主题概念", "范畴分类"])
    use_weight = kos_config.get("useWeight", "是")
    weight = float(kos_config.get("weight", 1))
    return_words = kos_config.get("returnWords", "是")

    # 文本预处理
    fragments = preprocess(text)

    # 术语识别
    matches = extract_terms(text)
    terms_in_doc: Dict[str, int] = Counter()
    for term, _start, _end in matches:
        terms_in_doc[term] += 1

    # TF-IDF 计算
    tfidf = compute_tfidf(fragments, terms_in_doc)

    # 权重处理
    if use_weight == "是" and weight != 1:
        for t in tfidf:
            tfidf[t] = round(tfidf[t] * weight, 4)

    # 构建三类实体
    term_entities, concept_entities, category_entities = build_concept_entities(
        terms_in_doc, tfidf, term_count
    )
    # 按配置截断概念/范畴数量
    concept_entities = concept_entities[:concept_count]
    category_entities = category_entities[:category_count]

    # 命名实体识别（组织机构/专家学者/学术期刊）
    named_entities: List[Dict[str, Any]] = []
    if any(et in entity_types for et in ["组织机构", "专家学者", "学术期刊"]):
        ne_results = extract_named_entities(text)
        if "组织机构" in entity_types:
            for name, _s, _e in ne_results["组织机构"]:
                named_entities.append({
                    "name": name, "type": "组织机构", "properties": {"source": "KOS内置词表"}
                })
        if "专家学者" in entity_types:
            for name, _s, _e in ne_results["专家学者"]:
                named_entities.append({
                    "name": name, "type": "专家学者", "properties": {"source": "KOS内置词表"}
                })
        if "学术期刊" in entity_types:
            for name, _s, _e in ne_results["学术期刊"]:
                named_entities.append({
                    "name": name, "type": "学术期刊", "properties": {"source": "KOS内置词表"}
                })

    # 按 entityTypes 过滤实体
    all_entities: List[Dict[str, Any]] = []
    if "高频术语" in entity_types:
        all_entities.extend(term_entities)
    if "主题概念" in entity_types:
        all_entities.extend(concept_entities)
    if "范畴分类" in entity_types:
        all_entities.extend(category_entities)
    all_entities.extend(named_entities)

    # 构建关系
    relations = build_relations(
        term_entities, concept_entities, category_entities, fragments, prefix
    )

    # 本体对齐：若 ontology 提供了实体类型，尝试将 KOS 类型映射到本体类型
    if ontology:
        all_entities, relations = _align_to_ontology(all_entities, relations, ontology)

    # returnWords 控制是否返回高频术语（默认是）
    if return_words == "否":
        all_entities = [e for e in all_entities if e["type"] != "高频术语"]

    return {
        "entities": all_entities,
        "relations": relations,
        "metrics": {
            "termCount": len(term_entities),
            "conceptCount": len(concept_entities),
            "categoryCount": len(category_entities),
            "namedEntityCount": len(named_entities),
        },
    }


def _align_to_ontology(
    entities: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    ontology: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    将 KOS 抽取的实体类型与当前图谱模型的本体 Schema 对齐。
    若本体中存在同义实体类型，则映射；否则保留 KOS 原始类型。
    """
    onto_entities = ontology.get("entities", []) or []
    onto_entity_names = {e.get("name") for e in onto_entities if e.get("name")}

    # KOS 类型 -> 本体类型映射规则（按名称包含关系）
    type_mapping: Dict[str, str] = {}
    kos_types = {"高频术语", "主题概念", "范畴分类", "组织机构", "专家学者", "学术期刊"}
    for kt in kos_types:
        for oe_name in onto_entity_names:
            # 简单包含匹配
            if kt in oe_name or oe_name in kt:
                type_mapping[kt] = oe_name
                break

    for e in entities:
        original_type = e.get("type")
        if original_type in type_mapping:
            e["properties"]["kosType"] = original_type
            e["type"] = type_mapping[original_type]

    return entities, relations
