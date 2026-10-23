# -*- coding: utf-8 -*-
"""去掉「系列内排名式」描述（全套里唯一 / 最短最好上手的一集 / 最X的一篇…）。

系列还在更新，按「34 集里唯一/最短」写会过时，也不该当成卖点。
就地文本替换（不做 JSON 反序列化，避免重排格式），每条断言必须命中 1 次。
用法: python tools/fix_blurbs.py [--dry]
"""
import io, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
L = os.path.join(BASE, "lessons")

R = [
    # 04
    ("04-sand-play.json",
     "句子都很短，是最适合张口跟读的一篇。",
     "句子都很短，很适合张口跟读。"),
    # 05
    ("05-brush-teeth.json",
     "语速偏快、从句多，是全套里长难句最集中的一篇",
     "语速偏快、从句多，长难句集中"),
    # 06
    ("06-wash-face.json",
     "句式超级规整，是全套里最适合开「挖空自测」的一篇。",
     "句式超级规整，很适合开「挖空自测」。"),
    ("06-wash-face.json",
     "句式规整、动词密集，最适合做「跟读 + 挖空自测」",
     "句式规整、动词密集，很适合做「跟读 + 挖空自测」"),
    # 07
    ("07-wash-hands.json",
     "句子全部短到一两秒，是最容易一次背下的一篇。",
     "句子全部短到一两秒，很容易一次背下来。"),
    # 08
    ("08-swing.json",
     "几乎全是一两秒的短句，是全套里最适合对着宝宝一句一句复述的一篇。",
     "几乎全是一两秒的短句，很适合对着宝宝一句一句复述。"),
    ("08-swing.json",
     "全是短句和反问，最适合跟宝宝一对一练习",
     "全是短句和反问，很适合跟宝宝一对一练习"),
    # 09
    ("09-grocery-shopping.json",
     "也是最适合带着孩子一起「实景学」的一篇。",
     "也很适合带着孩子一起「实景学」。"),
    # 10
    ("10-grocery-shopping-2.json",
     "这一整套句子几乎能原封不动用在任何一家美国超市，是这套系列里「最能直接用上」的一集。",
     "这一整套句子几乎能原封不动用在任何一家美国超市。"),
    # 11
    ("11-trim-nails.json",
     "这一段是全集最实用的动作句",
     "这一段是很实用的动作句"),
    # 12
    ("12-playdough.json",
     "玩橡皮泥这一集，是全套里「动词最密集」的一集：",
     "玩橡皮泥这一集，动词很密集："),
    # 13
    ("13-coloring.json",
     "句子短、重复多，是最适合「跟着做一遍」的一集。",
     "句子短、重复多，很适合「跟着做一遍」。"),
    ("13-coloring.json",
     "这是全套里最值得背的一个动词短语， kids 涂色、画画、吃点心全用得上。",
     "这是很值得背的一个动词短语，涂色、画画、吃点心全用得上。"),
    # 14
    ("14-dragon-boat-festival.json",
     "全套 34 集里唯一讲「中国节日」的一集，也是唯一一集有完整食谱的：先讲端午节的由来",
     "先讲端午节的由来"),
    ("14-dragon-boat-festival.json",
     "步骤词密集（soak / fold / roll / cover / wrap / boil / simmer），是这套里最「能回家照着做」的一集。",
     "步骤词密集（soak / fold / roll / cover / wrap / boil / simmer），是可以回家照着做的一集。"),
    ("14-dragon-boat-festival.json",
     "中式节日唯一一集：端午由来 + 包粽子全流程",
     "中式节日主题：端午由来 + 包粽子全流程"),
    ("14-dragon-boat-festival.json",
     "（用叶子盖住米）。cover 是这套里超实用的一词。",
     "（用叶子盖住米）。cover 是很实用的一个词。"),
    # 15
    ("15-bubbles.json",
     "全套里最短最好上手的一集：一对双胞胎第一次真正玩上泡泡",
     "一对双胞胎第一次真正玩上泡泡"),
    ("15-bubbles.json",
     "全篇都是短句：吹泡泡这套动词最简单最好模仿",
     "全篇都是短句：吹泡泡的动词好模仿"),
    # 16
    ("16-scooter.json",
     "夸奖句型密度是全套里最高的，孩子一天就能背下来五句。",
     "夸奖句型密度很高，孩子一天就能背下来五句。"),
    ("16-scooter.json",
     "全篇围绕「戴头盔」这一件事，安全句型最好背",
     "全篇围绕「戴头盔」这一件事，安全句型好背"),
    # 17
    ("17-peekaboo.json",
     "方位词 + 数数 + 找人，三个最实用的语言板块一次打包",
     "方位词 + 数数 + 找人，三个很实用的语言板块一次打包"),
    # 18
    ("18-bike-riding.json",
     "全场最「有故事」的一集：给 Ryan 套上护肘",
     "这一集很有故事：给 Ryan 套上护肘"),
    ("18-bike-riding.json",
     "字汇最实用的一集：护具、平衡、放手、坚持，全是家长当场要用的词",
     "护具、平衡、放手、坚持，全是家长当场要用的词"),
    # 19
    ("19-playground-safety-1.json",
     "全套里最实用的安全句型：不许跑、轮流玩、别从高处跳",
     "安全句型很实用：不许跑、轮流玩、别从高处跳"),
    # 21
    ("21-playground-equipment.json",
     "全套里唯一的「名词课」，也是最好用的一集：姐姐带着妹妹",
     "这一集是「名词课」：姐姐带着妹妹"),
    ("21-playground-equipment.json",
     "是照着实物学名词的最佳素材。",
     "是照着实物学名词的好素材。"),
    # 22
    ("22-feeding-baby.json",
     "这一集和前 21 集都不一样——它不是跟孩子对话，而是妈妈对着镜头讲",
     "这一集不是跟孩子对话，而是妈妈对着镜头讲"),
    ("22-feeding-baby.json",
     "唯一一集「家长视角」的育儿知识：",
     "「家长视角」的育儿知识："),
    # 24
    ("24-potty-training.json",
     "全套里最「真实」的一集：包括失败、抗拒和放弃",
     "很「真实」的一集：包括失败、抗拒和放弃"),
    # 25
    ("25-bus-safety.json",
     "全套里 Never 最多的一集：六条禁令一次说清",
     "六条 Never 禁令一次说清"),
    # 26
    ("26-putting-on-socks.json",
     "只要三步、句型极短，是「自己穿衣」系列最好入门的一集",
     "只要三步、句型极短，入门很快"),
    # 28
    ("28-baby-clothes-words.json",
     "最适合当「宝宝衣物英文小词典」收藏",
     "很适合当「宝宝衣物英文小词典」收藏"),
    # 29
    ("29-tying-shoelaces.json",
     "整套动作词密度最高的一集，cross / pinch",
     "动作词密度高：cross / pinch"),
    # 30
    ("30-zipping-up.json",
     "只有 1 分钟，但把「拉链的原理」讲得最清楚的一集",
     "只有 1 分钟，却把「拉链的原理」讲得很清楚"),
    # 31
    ("31-buttons.json",
     "扣扣子是手部精细动作的天花板，这集把原理讲得最细",
     "扣扣子是手部精细动作的天花板，这集把原理讲得很细"),
    # 33
    ("33-putting-on-pants.json",
     "「坐着穿 + 拇指在裤腰里面」两个关键点讲得最清楚",
     "「坐着穿 + 拇指在裤腰里面」两个关键点讲得很清楚"),
    # 34
    ("34-putting-on-jacket.json",
     "穿衣系列的最后一课，也是最难的一个——穿外套要同时处理两件事",
     "穿外套要同时处理两件事"),
    ("34-putting-on-jacket.json",
     "袖子（bunched up 的麻烦）和扣子。视频给了两个特别实用的技巧：",
     "袖子（bunched up 的麻烦）和扣子，是这组自理动作里最难的一步。视频给了两个特别实用的技巧："),
]


def main():
    dry = "--dry" in sys.argv
    bad, cache = [], {}
    for fn, old, new in R:
        p = os.path.join(L, fn)
        if p not in cache:
            cache[p] = io.open(p, encoding="utf-8").read()
        n = cache[p].count(old)
        if n != 1:
            bad.append((fn, n, old[:44]))
            continue
        cache[p] = cache[p].replace(old, new)
    if bad:
        print("!! 有 %d 条没命中，未写入：" % len(bad))
        for fn, n, s in bad:
            print("   %-34s 命中 %d 次 :: %s" % (fn, n, s))
        return
    if dry:
        print("dry-run：%d 条全部命中 1 次，涉及 %d 个文件" % (len(R), len(cache)))
        return
    for p, txt in cache.items():
        io.open(p, "w", encoding="utf-8").write(txt)
    print("已写入 %d 个文件 / %d 处替换" % (len(cache), len(R)))


if __name__ == "__main__":
    main()
