import Discord from "discord.js";

const client = new Discord.Client({
    intents: [
        "Guilds",
        "GuildMessages",
        "MessageContent",
        "GuildMembers"
    ]
});

const PREFIX = "!";
const LOG_CHANNEL_ID = "1454209918432182404";


// ========================
// 等级顺序（从低到高）
// ========================

const RANK_ORDER = [

    "服务领队",
    "初级管理员",
    "高级管理员",

    "主管",
    "经理",

    "初级公司",
    "执行实习生",
    "执行官",
    "副总裁",
    "总裁",

    "副主席",
    "主席",
    "理事会实习生",
    "星球委员会",
    "执行委员会",
    "外星委员会",

    "领导力实习生",
    "专员",
    "社区官员",

    "社区经理",
    "共同所有人",
    "所有者",
    "持有者"
];


// ========================
// 档次
// ========================

const RANK_TIERS = [

    { keyword: "LR", min: 0, max: 2 },
    { keyword: "MR", min: 3, max: 4 },
    { keyword: "HR", min: 5, max: 9 },
    { keyword: "SHR", min: 10, max: 15 },
    { keyword: "Leadership Rank", min: 16, max: 18 },
    { keyword: "Ownership Rank", min: 19, max: 22 }

];


// ========================
// 获取职位（模糊识别）
// ========================

function getUserRank(member) {

    for (let role of member.roles.cache.values()) {

        let roleName = role.name.toLowerCase();

        for (let i = 0; i < RANK_ORDER.length; i++) {

            if (roleName.includes(RANK_ORDER[i].toLowerCase())) {

                return {
                    index: i,
                    name: RANK_ORDER[i],
                    role: role
                };
            }
        }
    }

    return null;
}


// ========================
// 找角色
// ========================

function findRole(guild, name) {

    return guild.roles.cache.find(
        r => r.name.includes(name)
    );
}


// ========================
// 获取档次
// ========================

function getTier(index) {

    for (let tier of RANK_TIERS) {

        if (index >= tier.min && index <= tier.max) {

            return tier.keyword;
        }
    }

    return "Unknown";
}


// ========================
// 启动
// ========================

client.once("ready", () => {

    console.log(`机器人上线: ${client.user.tag}`);
});


// ========================
// 指令系统
// ========================

client.on("messageCreate", async (msg) => {

    if (msg.author.bot) return;
    if (!msg.content.startsWith(PREFIX)) return;

    const args = msg.content.slice(PREFIX.length).trim().split(/ +/);
    const cmd = args.shift().toLowerCase();


    // ========================
    // 查看职位
    // ========================

    if (cmd === "myrank") {

        const info = getUserRank(msg.member);

        if (!info) {
            return msg.reply("未检测到职位");
        }

        msg.reply(
            `你的职位: ${info.name}\n等级: ${info.index}\n档次: ${getTier(info.index)}`
        );
    }


    // ========================
    // 晋升
    // ========================

    if (cmd === "promote") {

        const target = msg.mentions.members.first();

        if (!target) return msg.reply("请@成员");

        if (target.id === msg.author.id) {
            return msg.reply("不能晋升自己");
        }

        const myRank = getUserRank(msg.member);
        const targetRank = getUserRank(target);

        if (!myRank) return msg.reply("你没有职位");
        if (!targetRank) return msg.reply("目标没有职位");

        // SHR权限

        if (myRank.index < 10) {
            return msg.reply("只有 SHR / Leadership / Ownership 可以晋升");
        }

        // 不能操作同级或更高

        if (targetRank.index >= myRank.index) {
            return msg.reply("不能晋升同级或更高职位的人");
        }

        const nextIndex = targetRank.index + 1;

        if (nextIndex >= RANK_ORDER.length) {
            return msg.reply("已经是最高职位");
        }

        const newRole = findRole(msg.guild, RANK_ORDER[nextIndex]);

        if (!newRole) return msg.reply("找不到下一级职位");

        await target.roles.remove(targetRank.role);
        await target.roles.add(newRole);

        msg.channel.send(
            `成功晋升 ${target.user.username}\n${targetRank.name} → ${RANK_ORDER[nextIndex]}`
        );

        // 日志

        const logChannel = msg.guild.channels.cache.get(LOG_CHANNEL_ID);

        if (logChannel) {

            logChannel.send(
`📈 晋升记录

操作人: ${msg.author.tag}
目标: ${target.user.tag}

原职位: ${targetRank.name}
新职位: ${RANK_ORDER[nextIndex]}

时间: <t:${Math.floor(Date.now()/1000)}:F>`
            );
        }
    }


    // ========================
    // 降级
    // ========================

    if (cmd === "demote") {

        const target = msg.mentions.members.first();

        if (!target) return msg.reply("请@成员");

        if (target.id === msg.author.id) {
            return msg.reply("不能降级自己");
        }

        const myRank = getUserRank(msg.member);
        const targetRank = getUserRank(target);

        if (!myRank) return msg.reply("你没有职位");
        if (!targetRank) return msg.reply("目标没有职位");

        if (myRank.index < 10) {
            return msg.reply("只有 SHR / Leadership / Ownership 可以降级");
        }

        if (targetRank.index >= myRank.index) {
            return msg.reply("不能降级同级或更高职位的人");
        }

        const prevIndex = targetRank.index - 1;

        if (prevIndex < 0) {
            return msg.reply("已经是最低职位");
        }

        const newRole = findRole(msg.guild, RANK_ORDER[prevIndex]);

        if (!newRole) return msg.reply("找不到下一级职位");

        await target.roles.remove(targetRank.role);
        await target.roles.add(newRole);

        msg.channel.send(
            `成功降级 ${target.user.username}\n${targetRank.name} → ${RANK_ORDER[prevIndex]}`
        );

        // 日志

        const logChannel = msg.guild.channels.cache.get(LOG_CHANNEL_ID);

        if (logChannel) {

            logChannel.send(
`📉 降级记录

操作人: ${msg.author.tag}
目标: ${target.user.tag}

原职位: ${targetRank.name}
新职位: ${RANK_ORDER[prevIndex]}

时间: <t:${Math.floor(Date.now()/1000)}:F>`
            );
        }
    }

});


// ========================
// 登录
// ========================

client.login("你的TOKEN");
