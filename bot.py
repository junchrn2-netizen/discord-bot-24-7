# 军事管理 Bot v12 - 5秒规则显示
import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# 🛡️ 内务部门 ID
# ─────────────────────────────────────────────
INTERNAL_AFFAIRS_ROLE = 1505175647989923941

# ─────────────────────────────────────────────
# 🕐 每个职级的晋升冷却时间（小时）
# ─────────────────────────────────────────────
PROMOTE_CD_HOURS = [
    0,    # 0: 市民
    3,    # 1: 新兵
    6,    # 2: 列兵
    12,   # 3: 下士
    15,   # 4: 三级军士长
    20,   # 5: 二级军士长
    25,   # 6: 一级军士长
    30,   # 7: 少尉(特殊)
    35,   # 8: 学员
    40,   # 9: 初级军官
    45,   # 10: 少尉
    50,   # 11: 中尉
    55,   # 12: 上尉
    60,   # 13: 少校
    65,   # 14: 中校
    70,   # 15: 上校
    75,   # 16: 旅长
    80,   # 17: 师长
    85,   # 18: 陆军上将
    250,  # 19: 军事精英
    500,  # 20: 皇家精英
    350,  # 21: 秘密精英
]

# ─────────────────────────────────────────────
# 🔰 军事职级 ID
# ─────────────────────────────────────────────
RANK_IDS = [
    1404135688991015083, # 0: 市民
    1428876572064223322, # 1: 新兵
    1433151035605647413, # 2: 列兵
    1474453339969290393, # 3: 下士
    1474453748976849057, # 4: 三级军士长
    1474454248057212939, # 5: 二级军士长
    1474454457428344913, # 6: 一级军士长
    1474454651477950536, # 7: 少尉 (特殊)
    1478803086737801286, # 8: 学员
    1474455128915574976, # 9: 初级军官
    1474455312185430097, # 10: 少尉
    1474455618763882725, # 11: 中尉
    1474455834883784837, # 12: 上尉
    1474456027821904018, # 13: 少校
    1474456175129919489, # 14: 中校
    1474456544903958685, # 15: 上校
    1474456713246674996, # 16: 旅长
    1474456935800770753, # 17: 师长
    1474457200478126194, # 18: 陆军上将
    1474457093833490575, # 19: 军事精英
    1505253473690587147, # 20: 皇家精英
    1474457288881213613  # 21: 秘密精英
]

# 🗂️ 阶级/档次 ID 配置
TIER_CONFIG = [
    {"name": "士兵",       "id": 1505251007297486928, "min": 1,  "max": 3},
    {"name": "毕业生",     "id": 1474458514721083514, "min": 4,  "max": 6},
    {"name": "特殊军衔",   "id": 1474458682027937863, "min": 7,  "max": 8},
    {"name": "初级军官",   "id": 1474458976849629227, "min": 9,  "max": 10},
    {"name": "中级军官",   "id": 1505253862817140803, "min": 11, "max": 12},
    {"name": "高级军官",   "id": 1505254019772186694, "min": 13, "max": 15},
    {"name": "将军",       "id": 1474459321906626818, "min": 16, "max": 18},
    {"name": "精英军官",   "id": 1474459473920917576, "min": 19, "max": 21},
]

RANK_NAMES = {
    "市民": 0, "平民": 0,
    "新兵": 1, "列兵": 2, "下士": 3,
    "三级军士长": 4, "二级军士长": 5, "一级军士长": 6,
    "少尉特殊": 7, "学员": 8, "初级军官": 9,
    "少尉": 10, "中尉": 11, "上尉": 12,
    "少校": 13, "中校": 14, "上校": 15,
    "旅长": 16, "师长": 17, "陆军上将": 18,
    "军事精英": 19, "皇家精英": 20, "秘密精英": 21,
}

LOG_RANK_CHANGE = 1454209918432182404

# ─────────────────────────────────────────────
# 🤖 逻辑核心
# ─────────────────────────────────────────────

def get_rank_index(member):
    m_role_ids = [r.id for r in member.roles]
    for i in range(len(RANK_IDS)):
        if RANK_IDS[i] in m_role_ids:
            return i
    return -1

def get_tier_info(index):
    for t in TIER_CONFIG:
        if t["min"] <= index <= t["max"]:
            return t
    return None

def has_internal_affairs(member):
    return any(r.id == INTERNAL_AFFAIRS_ROLE for r in member.roles)

class MilitaryBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

bot = MilitaryBot()
op_lock = asyncio.Lock()
last_promotion = {}

# ─────────────────────────────────────────────
# 🚀 权限判定
# ─────────────────────────────────────────────

def check_permission(my_idx, target_idx, is_ia=False):
    if is_ia:
        return True, ""
    if my_idx < 9:
        return False, "❌ 你的职级太低。"
    if my_idx >= 16:
        if my_idx > target_idx:
            return True, ""
        return False, "❌ 不能操作职级高于或等于你的人。"
    if 9 <= my_idx <= 15:
        if target_idx <= 6:
            return True, ""
        return False, "❌ 仅有权晋升/降级士兵和毕业生。"
    return False, "❌ 权限错误。"

# ─────────────────────────────────────────────
# ⚔️ 晋升/降级/流放/setrank
# ─────────────────────────────────────────────

async def process_military_rank(ctx_or_interaction, member, direction, reason=None):
    async with op_lock:
        if isinstance(ctx_or_interaction, discord.Interaction):
            interaction = ctx_or_interaction
            await interaction.response.defer()
            invoker = interaction.user
            followup = interaction.followup
        else:
            ctx = ctx_or_interaction
            invoker = ctx.author
            followup = ctx
        member = await ctx_or_interaction.guild.fetch_member(member.id)
        if has_internal_affairs(member):
            return await followup.send("🛡️ 目标属于内务部门，不可被操作。")
        invoker_is_ia = has_internal_affairs(invoker)
        my_idx = get_rank_index(invoker)
        t_idx = get_rank_index(member)
        if t_idx == -1:
            return await followup.send("❌ 无法识别目标的职级。")
        if direction == 1:
            now = datetime.now()
            if member.id in last_promotion:
                cd_hours = PROMOTE_CD_HOURS[t_idx]
                elapsed = (now - last_promotion[member.id]).total_seconds() / 3600
                remaining_hours = cd_hours - elapsed
                if remaining_hours > 0:
                    if remaining_hours >= 1:
                        return await followup.send(f"⏳ {member.mention} 还需等待 **{remaining_hours:.1f} 小时**才能晋升！")
                    else:
                        mins = int(remaining_hours * 60)
                        return await followup.send(f"⏳ {member.mention} 还需等待 **{mins} 分钟**才能晋升！")
        can_proceed, error_msg = check_permission(my_idx, t_idx, invoker_is_ia)
        if not can_proceed:
            return await followup.send(error_msg)
        new_idx = t_idx + direction
        if new_idx < 0 or new_idx >= len(RANK_IDS):
            return await followup.send("❌ 职级已达极限。")
        await apply_rank_change(ctx_or_interaction, member, invoker, t_idx, new_idx, followup, reason=reason)

async def process_exile(ctx_or_interaction, member, reason=None):
    async with op_lock:
        if isinstance(ctx_or_interaction, discord.Interaction):
            interaction = ctx_or_interaction
            await interaction.response.defer()
            invoker = interaction.user
            followup = interaction.followup
        else:
            ctx = ctx_or_interaction
            invoker = ctx.author
            followup = ctx
        member = await ctx_or_interaction.guild.fetch_member(member.id)
        if has_internal_affairs(member):
            return await followup.send("🛡️ 目标属于内务部门，不可被流放。")
        invoker_is_ia = has_internal_affairs(invoker)
        my_idx = get_rank_index(invoker)
        t_idx = get_rank_index(member)
        if t_idx == -1:
            return await followup.send("❌ 无法识别目标的职级。")
        if t_idx == 0:
            return await followup.send("❌ 目标已经是市民。")
        can_proceed, error_msg = check_permission(my_idx, t_idx, invoker_is_ia)
        if not can_proceed:
            return await followup.send(error_msg)
        await apply_rank_change(ctx_or_interaction, member, invoker, t_idx, 0, followup, is_exile=True, reason=reason)

async def process_setrank(ctx_or_interaction, member, rank_name, reason=None):
    async with op_lock:
        if isinstance(ctx_or_interaction, discord.Interaction):
            interaction = ctx_or_interaction
            await interaction.response.defer()
            invoker = interaction.user
            followup = interaction.followup
        else:
            ctx = ctx_or_interaction
            invoker = ctx.author
            followup = ctx
        member = await ctx_or_interaction.guild.fetch_member(member.id)
        if has_internal_affairs(member):
            return await followup.send("🛡️ 目标属于内务部门。")
        if not has_internal_affairs(invoker):
            return await followup.send("❌ 只有内务部门可以使用。")
        new_idx = None
        for name, idx in RANK_NAMES.items():
            if name.lower() == rank_name.lower():
                new_idx = idx
                break
        if new_idx is None:
            return await followup.send(f"❌ 未知职级。")
        t_idx = get_rank_index(member)
        if t_idx == -1:
            return await followup.send("❌ 无法识别目标的职级。")
        if t_idx == new_idx:
            return await followup.send(f"❌ 已经是该职级。")
        await apply_rank_change(ctx_or_interaction, member, invoker, t_idx, new_idx, followup, is_setrank=True, reason=reason)

async def apply_rank_change(ctx_or_interaction, member, invoker, old_idx, new_idx, followup, is_exile=False, is_setrank=False, reason=None):
    old_pos_role = ctx_or_interaction.guild.get_role(RANK_IDS[old_idx])
    new_pos_role = ctx_or_interaction.guild.get_role(RANK_IDS[new_idx])
    old_t_cfg = get_tier_info(old_idx)
    new_t_cfg = get_tier_info(new_idx)
    add_list, rem_list = [new_pos_role], [old_pos_role]
    if is_exile or is_setrank:
        for i in range(1, len(RANK_IDS)):
            role = ctx_or_interaction.guild.get_role(RANK_IDS[i])
            if role and role in member.roles:
                rem_list.append(role)
        for tier in TIER_CONFIG:
            role = ctx_or_interaction.guild.get_role(tier["id"])
            if role and role in member.roles:
                rem_list.append(role)
    else:
        if new_t_cfg:
            if not old_t_cfg or old_t_cfg["id"] != new_t_cfg["id"]:
                add_list.append(ctx_or_interaction.guild.get_role(new_t_cfg["id"]))
        if old_t_cfg:
            if not new_t_cfg or old_t_cfg["id"] != new_t_cfg["id"]:
                rem_list.append(ctx_or_interaction.guild.get_role(old_t_cfg["id"]))
    if is_setrank and new_t_cfg:
        add_list.append(ctx_or_interaction.guild.get_role(new_t_cfg["id"]))
    try:
        add_list = list(set([r for r in add_list if r]))
        rem_list = list(set([r for r in rem_list if r and r in member.roles]))
        await member.add_roles(*add_list)
        await member.remove_roles(*rem_list)
        now = datetime.now()
        last_promotion[member.id] = now
        if is_exile:
            title, color = "🚫 流放", discord.Color.dark_red()
        elif is_setrank:
            title, color = "📋 军衔授予", discord.Color.blue()
        else:
            title = "🎖️ 军事职级变动"
            color = discord.Color.gold() if new_idx > old_idx else discord.Color.light_gray()
        embed = discord.Embed(title=title, color=color, timestamp=now)
        embed.add_field(name="目标", value=member.mention, inline=True)
        embed.add_field(name="执行官", value=invoker.mention, inline=True)
        embed.add_field(name="变动", value=f"<@&{RANK_IDS[old_idx]}> ➔ <@&{RANK_IDS[new_idx]}>", inline=False)
        if not is_exile and old_t_cfg and new_t_cfg and old_t_cfg["id"] != new_t_cfg["id"]:
            embed.add_field(name="阶级", value=f"`{old_t_cfg['name']}` ➔ `{new_t_cfg['name']}`")
        elif not is_exile and new_t_cfg and not old_t_cfg:
            embed.add_field(name="阶级", value=f"`无` ➔ `{new_t_cfg['name']}`")
        if reason:
            embed.add_field(name="原因", value=reason, inline=False)
        next_cd = PROMOTE_CD_HOURS[new_idx]
        if next_cd > 0 and not is_exile:
            embed.set_footer(text=f"⏳ 下次晋升需等待 {next_cd} 小时")
        await followup.send(embed=embed)
        log_chan = bot.get_channel(LOG_RANK_CHANGE)
        if log_chan:
            await log_chan.send(embed=embed)
    except Exception as e:
        await followup.send(f"❌ 操作失败: {e}")

# ─────────────────────────────────────────────
# 📋 训练系统数据
# ─────────────────────────────────────────────

CIVILIAN_RULES = [
    ("🏙️ 你将以\"市民\"身份加入服务器。",
     "加入后你的初始身份是？",
     ["军官", "市民", "新兵"], 1),
    ("🏙️ 参加新兵招募训练，了解基本纪律和规则。",
     "成为新兵前需要做什么？",
     ["直接当军官", "参加新兵招募训练", "什么都不做"], 1),
    ("🏙️ 认真听完教官宣读的规则，即可获得 1 分。",
     "听完规则可以获得什么？",
     ["1 分", "100 元", "立刻成为将军"], 0),
    ("🏙️ 完成基础训练后，将由教官晋升为\"新兵\"。",
     "完成基础训练后你会？",
     ["被降级", "被晋升为新兵", "被流放"], 1),
    ("🏙️ 作为市民，请勿进入军事训练区域，除非得到许可。",
     "市民可以随意进入军事训练区吗？",
     ["可以", "不可以，需得到许可", "随时都能进"], 1),
    ("🏙️ 尊重所有军人，保持礼貌和友善。",
     "对待军人应该？",
     ["不礼貌", "尊重和友善", "无视"], 1),
    ("🏙️ 如有任何问题，可联系招募官或初级军官。",
     "有疑问时应该找谁？",
     ["自己猜", "招募官或初级军官", "谁也不找"], 1),
]

MILITARY_RULES = [
    ("⚔️ 绝对服从上级军官的命令，不得违抗。",
     "上级军官下达命令时，你应该？",
     ["先考虑对自己是否有利", "绝对服从，不得违抗", "假装没听到"], 1),
    ("⚔️ 训练期间必须保持队列整齐，禁止随意走动。",
     "训练期间你可以？",
     ["随意走动", "保持队列整齐", "坐下休息"], 1),
    ("⚔️ 未经教官允许，严禁发言。如需发言，请说\"请求发言\"。",
     "训练中想说话时，你应该？",
     ["直接大声说", "举手就行", "说\"请求发言\"等待批准"], 2),
    ("⚔️ 严禁在训练频道内争吵、辱骂或挑衅他人。",
     "和战友发生矛盾时，你应该？",
     ["当场吵一架", "辱骂对方", "保持冷静，报告上级"], 2),
    ("⚔️ 迟到者需向教官申请后方可加入训练，否则视为缺席。",
     "训练迟到了，你应该？",
     ["直接溜进去", "不参加了", "向教官申请批准后加入"], 2),
    ("⚔️ 训练中不得质疑教官的评分和指令。",
     "对教官的评分有疑问时，你应该？",
     ["当场质疑", "训练结束后私下沟通", "骂教官"], 1),
    ("⚔️ 禁止冒充军官或使用非自身职级的身份组。",
     "关于身份组，哪个正确？",
     ["可以用任何身份组", "只能使用自己职级的身份组", "可以冒充军官"], 1),
    ("⚔️ 训练期间必须穿着规定制服，保持仪表整洁。",
     "训练时应该穿什么？",
     ["随便穿", "规定制服，保持整洁", "睡衣"], 1),
    ("⚔️ 泄露军事机密或训练内容给非军事人员，将被严惩。",
     "把训练内容告诉外人，会怎样？",
     ["没关系", "被表扬", "被严惩"], 2),
    ("⚔️ 违反以上规定者，视情节给予扣分、降级或流放处罚。",
     "违反纪律的后果不包括？",
     ["扣分", "降级", "发奖金"], 2),
]

# ─────────────────────────────────────────────
# 🎓 一键训练系统
# ─────────────────────────────────────────────

class TrainingView(discord.ui.View):
    def __init__(self, member, trainer, rules, training_type):
        super().__init__(timeout=600)
        self.member = member
        self.trainer = trainer
        self.rules = rules
        self.training_type = training_type
        self.current_rule = 0
        self.total = len(rules)
        self.score = 0
        self.rule_msg = None
        self.quiz_msg = None

    async def start(self, channel):
        await self.show_rule(channel)

    async def show_rule(self, channel):
        if self.current_rule >= self.total:
            await self.finish(channel)
            return

        rule_text, question, options, correct = self.rules[self.current_rule]
        idx = self.current_rule + 1

        embed = discord.Embed(
            title=f"{'🏙️' if self.training_type == 'civilian' else '⚔️'} 规则 {idx}/{self.total}",
            description=rule_text,
            color=discord.Color.blue()
        )
        self.rule_msg = await channel.send(embed=embed)

        await asyncio.sleep(5)
        if self.rule_msg:
            await self.rule_msg.delete()
            self.rule_msg = None

        view = QuizView(self, correct, options, self.member)
        embed = discord.Embed(
            title=f"❓ 第 {idx} 题",
            description=f"{question}\n\n🅰️ {options[0]}\n🅱️ {options[1]}\n🅲️ {options[2]}",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"{self.member.display_name} 请选择答案")
        self.quiz_msg = await channel.send(embed=embed, view=view)

    async def next_rule(self, channel):
        self.current_rule += 1
        if self.quiz_msg:
            await self.quiz_msg.delete()
            self.quiz_msg = None
        await self.show_rule(channel)

    async def fail(self, channel):
        await channel.send(
            f"❌ {self.member.mention} 答错了！训练失败，请重新开始。",
            delete_after=10
        )
        if self.quiz_msg:
            await self.quiz_msg.delete()

    async def finish(self, channel):
        self.score += 1
        await channel.send(
            f"✅ {self.member.mention} 完成了所有规则训练！获得 **{self.score} 分**！\n"
            f"🎖️ 教官 {self.trainer.mention} 可以晋升该成员了。"
        )


class QuizView(discord.ui.View):
    def __init__(self, training, correct_idx, options, member):
        super().__init__(timeout=15)
        self.training = training
        self.correct_idx = correct_idx
        self.member = member
        self.answered = False

        labels = ["🅰️", "🅱️", "🅲️"]
        for i, opt in enumerate(options):
            btn = discord.ui.Button(label=f"{labels[i]} {opt}", style=discord.ButtonStyle.secondary, row=0)
            btn.callback = self.make_callback(i)
            self.add_item(btn)

    def make_callback(self, idx):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.member.id:
                await interaction.response.send_message("❌ 只有受训者可以作答！", ephemeral=True)
                return
            if self.answered:
                await interaction.response.send_message("⏰ 已经回答过了！", ephemeral=True)
                return
            self.answered = True
            for child in self.children:
                child.disabled = True
            if idx == self.correct_idx:
                await interaction.response.edit_message(view=self)
                await self.training.next_rule(interaction.channel)
            else:
                await interaction.response.edit_message(view=self)
                await self.training.fail(interaction.channel)
        return callback

    async def on_timeout(self):
        if not self.answered:
            self.answered = True
            for child in self.children:
                child.disabled = True
            if self.training.quiz_msg:
                await self.training.quiz_msg.edit(view=self)
            await self.training.fail(self.training.quiz_msg.channel if self.training.quiz_msg else None)


async def process_train(ctx_or_interaction, member):
    if isinstance(ctx_or_interaction, discord.Interaction):
        interaction = ctx_or_interaction
        await interaction.response.defer()
        invoker = interaction.user
        channel = interaction.channel
    else:
        ctx = ctx_or_interaction
        invoker = ctx.author
        channel = ctx.channel

    member = await ctx_or_interaction.guild.fetch_member(member.id)

    invoker_idx = get_rank_index(invoker)
    is_ia = has_internal_affairs(invoker)
    t_idx = get_rank_index(member)

    if t_idx == -1:
        msg = "❌ 无法识别目标的职级。"
        if isinstance(ctx_or_interaction, discord.Interaction):
            return await interaction.followup.send(msg)
        else:
            return await channel.send(msg)

    if t_idx == 0:
        if invoker_idx < 4 and not is_ia:
            msg = "❌ 招募平民需要三级军士长及以上职级。"
            if isinstance(ctx_or_interaction, discord.Interaction):
                return await interaction.followup.send(msg)
            else:
                return await channel.send(msg)
        rules = CIVILIAN_RULES
        training_type = "civilian"
        type_name = "🏙️ 平民招募训练"
    else:
        if invoker_idx < 9 and not is_ia:
            msg = "❌ 训练军人需要初级军官及以上职级。"
            if isinstance(ctx_or_interaction, discord.Interaction):
                return await interaction.followup.send(msg)
            else:
                return await channel.send(msg)
        rules = MILITARY_RULES
        training_type = "military"
        type_name = "⚔️ 军人规则训练"

    embed = discord.Embed(
        title=type_name,
        description=f"{member.mention} 的训练开始！\n📋 共 {len(rules)} 条规则\n⏱️ 每条规则显示 5 秒后出题\n🎯 答错即终止",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"教官：{invoker.display_name}")

    if isinstance(ctx_or_interaction, discord.Interaction):
        await interaction.followup.send(embed=embed)
    else:
        await channel.send(embed=embed)

    await asyncio.sleep(2)

    view = TrainingView(member, invoker, rules, training_type)
    await view.start(channel)

# ─────────────────────────────────────────────
# 📋 命令注册
# ─────────────────────────────────────────────

@bot.tree.command(name="train", description="一键训练（自动判断平民/军人）")
@app_commands.describe(member="目标成员")
async def train_slash(interaction: discord.Interaction, member: discord.Member):
    await process_train(interaction, member)

@bot.command(name="train")
async def train_prefix(ctx: commands.Context, member: discord.Member):
    await process_train(ctx, member)

@bot.tree.command(name="promote", description="晋升成员的军事职级")
async def promote_slash(interaction: discord.Interaction, member: discord.Member):
    await process_military_rank(interaction, member, 1)

@bot.tree.command(name="demote", description="降级成员的军事职级")
@app_commands.describe(member="目标成员", reason="降级原因")
async def demote_slash(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await process_military_rank(interaction, member, -1, reason=reason)

@bot.tree.command(name="exile", description="流放成员")
@app_commands.describe(member="目标成员", reason="流放原因")
async def exile_slash(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await process_exile(interaction, member, reason=reason)

@bot.tree.command(name="setrank", description="直接授予军衔（内务部门）")
@app_commands.describe(member="目标成员", rank="职级名称", reason="原因")
async def setrank_slash(interaction: discord.Interaction, member: discord.Member, rank: str, reason: str = None):
    await process_setrank(interaction, member, rank, reason=reason)

@bot.command(name="promote")
async def promote_prefix(ctx: commands.Context, member: discord.Member):
    await process_military_rank(ctx, member, 1)

@bot.command(name="demote")
async def demote_prefix(ctx: commands.Context, member: discord.Member, *, reason: str = None):
    await process_military_rank(ctx, member, -1, reason=reason)

@bot.command(name="exile")
async def exile_prefix(ctx: commands.Context, member: discord.Member, *, reason: str = None):
    await process_exile(ctx, member, reason=reason)

@bot.command(name="setrank")
async def setrank_prefix(ctx: commands.Context, member: discord.Member, rank_name: str, *, reason: str = None):
    await process_setrank(ctx, member, rank_name, reason=reason)

@bot.command()
async def sync(ctx):
    synced = await bot.tree.sync()
    await ctx.send(f"✅ 已同步 {len(synced)} 个斜杠命令！")

@bot.event
async def on_ready():
    print(f"✅ 军事管理 Bot {bot.user} 已上线。")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
