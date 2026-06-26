"""生成3份证券知识测试 PDF 文档（ReportLab + macOS Chinese font）"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import ParagraphStyle

# Register Chinese font
ttf_path = "/System/Library/Fonts/STHeiti Medium.ttc"
pdfmetrics.registerFont(TTFont("STHeiti", ttf_path))

styles = {
    "title": ParagraphStyle("title", fontName="STHeiti", fontSize=18, textColor=HexColor("#0052CC"), spaceAfter=20),
    "page_num": ParagraphStyle("page", fontName="STHeiti", fontSize=9, textColor=HexColor("#86868b")),
    "heading": ParagraphStyle("heading", fontName="STHeiti", fontSize=14, spaceBefore=16, spaceAfter=12),
    "body": ParagraphStyle("body", fontName="STHeiti", fontSize=11, leading=18, spaceAfter=6),
}


def make_pdf(filename, title, pages):
    doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=50, bottomMargin=50)
    story = []
    for page_num, (heading, body) in enumerate(pages, 1):
        if page_num > 1:
            story.append(PageBreak())
        story.append(Paragraph(title, styles["title"]))
        story.append(Paragraph(f"第{page_num}页", styles["page_num"]))
        story.append(Paragraph(heading, styles["heading"]))
        for line in body.split("\n"):
            if line.strip():
                story.append(Paragraph(line.strip(), styles["body"]))
    doc.build(story)
    print(f"Created: {filename}")


make_pdf("data/证券基础知识.pdf", "证券基础知识手册", [
    ("什么是股票",
     "股票是股份有限公司发行的所有权凭证。股东凭持有股票享有公司收益分配权、\n"
     "股东大会投票权等权利。<br/><br/>"
     "A股：在中国内地上市的人民币普通股票，代码以600、000、002开头。<br/>"
     "H股：在香港上市的中国企业股票。<br/>"
     "科创板：专注于硬科技企业的板块，代码以688开头。<br/><br/>"
     "股票交易时间：周一至周五 9:30-11:30, 13:00-15:00。"),

    ("什么是债券",
     "债券是政府、企业等发行人向投资者发行的债务融资工具。<br/><br/>"
     "国债：由国家信用担保，风险最低，收益率通常作为市场基准利率。<br/>"
     "企业债：由企业发行，风险高于国债，收益率也相应较高。<br/>"
     "可转债：在特定条件下可转换为发行公司股票的特殊债券。<br/><br/>"
     "债券的核心要素：面值、票面利率、到期期限、发行人信用评级。"),

    ("什么是基金",
     "证券投资基金是通过发行基金份额募集资金，由基金管理人<br/>"
     "进行投资管理的集合投资方式。<br/><br/>"
     "按投资标的分类：<br/>"
     "- 股票型基金：80%以上资产投资于股票<br/>"
     "- 债券型基金：80%以上资产投资于债券<br/>"
     "- 混合型基金：股债比例灵活<br/>"
     "- 货币市场基金：投资于短期货币工具<br/><br/>"
     "ETF（交易型开放式指数基金）：在交易所上市交易，跟踪指数表现。"),
])

make_pdf("data/金融术语.pdf", "金融术语速查手册", [
    ("估值指标：PE与PB",
     "市盈率（PE）= 股价 ÷ 每股收益<br/>"
     "用于评估股票价格是否合理。高PE可能意味着市场预期高增长。<br/><br/>"
     "市净率（PB）= 股价 ÷ 每股净资产<br/>"
     "用于评估资产密集型企业的价值，银行业常用。<br/><br/>"
     "一般参考范围：<br/>"
     "- 大盘蓝筹股：PE 10-20倍<br/>"
     "- 成长股：PE 20-50倍<br/>"
     "- PB < 1 可能意味着股价低于净资产"),

    ("盈利指标：ROE与ROA",
     "净资产收益率（ROE）= 净利润 ÷ 股东权益<br/>"
     "衡量公司为股东创造利润的能力。ROE > 15%通常被认为优秀。<br/><br/>"
     "总资产收益率（ROA）= 净利润 ÷ 总资产<br/>"
     "衡量公司全部资产的盈利能力。<br/><br/>"
     "杜邦分析：ROE = 净利率 × 资产周转率 × 权益乘数<br/>"
     "通过拆解可以分析ROE的来源是盈利能力、运营效率还是财务杠杆。"),

    ("市场指标：指数与成交量",
     "上证指数：上海证券交易所的综合股价指数，反映A股整体走势。<br/>"
     "沪深300：沪深两市市值最大的300家公司，代表大盘蓝筹表现。<br/>"
     "创业板指：深交所创业板综合指数，代表成长型公司。<br/><br/>"
     "成交量：一定时间内成交的股票数量或金额。<br/>"
     "放量上涨说明买盘积极，缩量下跌说明抛压减弱。<br/><br/>"
     "换手率 = 成交量 ÷ 流通股本，反映股票交易活跃度。"),
])

make_pdf("data/投资风险与合规.pdf", "投资风险提示手册", [
    ("市场风险",
     "市场风险是证券价格因宏观经济因素波动导致损失的风险。<br/><br/>"
     "主要类型：<br/>"
     "1. 利率风险：利率上升导致债券价格下跌<br/>"
     "2. 汇率风险：本币贬值影响跨境投资收益<br/>"
     "3. 政策风险：监管政策变化影响特定行业<br/>"
     "4. 通胀风险：通货膨胀侵蚀实际购买力<br/><br/>"
     "应对策略：分散投资、定期定额、长期持有。"),

    ("信用风险与流动性风险",
     "信用风险：债券发行人无法按时还本付息的风险。<br/>"
     "评级越低、收益率越高的债券信用风险越大。<br/>"
     "投资者应关注发行人财务状况和信用评级变化。<br/><br/>"
     "流动性风险：无法及时以合理价格卖出资产的风险。<br/>"
     "小盘股、低评级债券通常流动性较差。<br/>"
     "流动性风险在市场恐慌时尤为突出。<br/><br/>"
     "建议：保持部分资产在高流动性产品中，如货币基金。"),

    ("投资者保护与合规要求",
     "证券投资者保护基金：当证券公司破产时，<br/>"
     "保护基金可对投资者进行有限赔付（最高50万元）。<br/><br/>"
     "适当性管理：券商应评估投资者的风险承受能力，<br/>"
     "推荐与其风险偏好相匹配的产品。<br/><br/>"
     "禁止行为：内幕交易、市场操纵、虚假陈述。<br/>"
     "投资者如发现违规行为可向证监会投诉举报。<br/><br/>"
     "投资前应阅读产品说明书和风险揭示书，<br/>"
     "充分了解产品特征和潜在风险。"),
])

print("\nDone! 3 test PDFs created in data/")
