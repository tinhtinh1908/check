"""Cleanup/setup profiles, ported 1:1 from ``@ANDROID.bat`` (menu items 1-5), plus the USB-debugging
guide (menu item 6). Step order matches the batch file; only exact duplicate lines were dropped.
``tests/test_profiles_parity.py`` re-parses the batch file to keep this module in sync.
"""

from __future__ import annotations

from dataclasses import dataclass

DOWNLOAD_DIR = "/sdcard/Download/"  # the batch used /sdcard/download: same folder on emulated storage
GBOARD_PKG = "com.google.android.inputmethod.latin"
GBOARD_IME = "com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME"


@dataclass(frozen=True, slots=True)
class Uninstall:
    pkg: str


@dataclass(frozen=True, slots=True)
class Disable:
    pkg: str


@dataclass(frozen=True, slots=True)
class Install:
    apk: str  # payload entry, e.g. "APK/1.CH_Play.apk"


@dataclass(frozen=True, slots=True)
class InstallMulti:
    apks: tuple[str, ...]
    label: str


@dataclass(frozen=True, slots=True)
class Push:
    apk: str
    dest: str = DOWNLOAD_DIR


@dataclass(frozen=True, slots=True)
class Shell:
    cmd: str
    label: str
    requires_pkg: str | None = None  # skip (do not fail) when this package is not installed
    may_disconnect: bool = False  # the command turns ADB off, so losing the device means success


Step = Uninstall | Disable | Install | InstallMulti | Push | Shell


@dataclass(frozen=True, slots=True)
class Profile:
    id: str
    name: str
    subtitle: str
    brands: tuple[str, ...]  # lower-case ro.product.brand / manufacturer values that match
    accent: str
    steps: tuple[Step, ...]
    note: str = ""
    post_note: str = ""

    def count(self, kind: type) -> int:
        return sum(1 for step in self.steps if isinstance(step, kind))

    @property
    def summary(self) -> str:
        parts = [
            ("Gỡ", self.count(Uninstall)),
            ("Tắt", self.count(Disable)),
            ("Cài", self.count(Install) + self.count(InstallMulti)),
            ("Chép", self.count(Push)),
        ]
        return " · ".join(f"{label} {n}" for label, n in parts if n)

    @property
    def short_summary(self) -> str:
        """Card-sized summary: installs and pushes counted together as APK files."""
        apk_count = self.count(Install) + self.count(InstallMulti) + self.count(Push)
        parts = []
        if removed := self.count(Uninstall):
            parts.append(f"Gỡ {removed}")
        if disabled := self.count(Disable):
            parts.append(f"Tắt {disabled}")
        if apk_count:
            parts.append(f"{apk_count} APK")
        return " · ".join(parts)

    def apks(self) -> list[str]:
        found: list[str] = []
        for step in self.steps:
            if isinstance(step, Install | Push):
                found.append(step.apk)
            elif isinstance(step, InstallMulti):
                found.extend(step.apks)
        return found


def uninstall(*pkgs: str) -> tuple[Uninstall, ...]:
    return tuple(Uninstall(p) for p in pkgs)


def disable(*pkgs: str) -> tuple[Disable, ...]:
    return tuple(Disable(p) for p in pkgs)


IME_ENABLE = Shell(f"ime enable {GBOARD_IME}", "Bật bàn phím Gboard", requires_pkg=GBOARD_PKG)
IME_SET = Shell(f"ime set {GBOARD_IME}", "Đặt Gboard làm bàn phím mặc định", requires_pkg=GBOARD_PKG)
CHROME_DEFAULT = Shell(
    "cmd role add-role-holder --user 0 android.app.role.BROWSER com.android.chrome",
    "Đặt Chrome làm trình duyệt mặc định",
    requires_pkg="com.android.chrome",
)
DEV_ON = Shell(
    "settings put global development_settings_enabled 1 && settings put global adb_enabled 1",
    "Giữ bật tùy chọn nhà phát triển và gỡ lỗi USB",
)
DEV_OFF = Shell(
    "settings put global development_settings_enabled 0 && settings put global adb_enabled 0",
    "Tắt tùy chọn nhà phát triển và gỡ lỗi USB",
    may_disconnect=True,
)
ZALO_SPLIT = InstallMulti(
    ("APK/Zalo/com.zing.zalo.apk", "APK/Zalo/config.arm64_v8a.apk", "APK/Zalo/config.hdpi.apk"), "Zalo"
)
FACEBOOK_SPLIT = InstallMulti(("APK/Facebook/com.facebook.katana.apk", "APK/Facebook/config.xxhdpi.apk"), "Facebook")

XIAOMI_POST_NOTE = (
    "Các file APK đã được chép vào thư mục Download (mở bằng ứng dụng Quản lý Tập tin). "
    "Để dùng chủ đề tiếng Việt: Settings (Cài đặt) → Back up and restore (Sao lưu và khôi phục) → "
    "Mobile devices (Thiết bị di động) → Khôi phục tập tin → thoát ra, vào lại ứng dụng Chủ đề và "
    "chọn chủ đề có tiếng Việt."
)

XIAOMI = Profile(
    id="xiaomi",
    name="Xiaomi / Redmi",
    subtitle="HyperOS · MIUI · POCO",
    brands=("xiaomi", "redmi", "poco"),
    accent="#FF6900",
    post_note=XIAOMI_POST_NOTE,
    steps=(
        *uninstall(
            "com.miui.fm",
            "com.ximalaya.ting.android",
            "com.baidu.BaiduMap",
            "com.ss.android.auto",
            "com.fenxiang.storyline",
            "com.tencent.qqlive",
            "com.jingdong.app.mall",
            "ctrip.android.view",
            "com.autonavi.minimap",
            "com.achievo.vipshop",
            "com.sdu.didi.psnger",
            "com.alibaba.wireless",
            "com.zhihu.android",
            "com.UCMobile",
            "com.dianping.v1",
            "com.qiyi.video",
            "com.xiaomi.aireco",
            "com.xiaomi.aiservice",
            "com.taobao.idlefish",
            "com.phoenix.read",
            "com.xs.fm",
            "com.dragon.read",
            "com.taobao.taobao",
            "com.ss.android.ugc.aweme",
            "com.xingin.xhs",
            "com.xiaomi.minigame",
            "com.quark.browser",
            "tv.danmaku.bili",
            "com.tongcheng.android",
            "com.xiaomi.xmsf",
            "com.sina.weibo",
            "com.sankuai.meituan",
            "com.smile.gifmaker",
            "com.xunmeng.pinduoduo",
            "com.baidu.searchbox",
            "com.ss.android.article.news",
            "com.eg.android.AlipayGphone",
            "net.huanci.hsjpro",
            "com.xiaomi.wpslauncher",
            "com.hongen.app.word",
            "com.ihuman.pinyin",
            "com.xiaomi.kidspace",
            "com.xiaomi.cajlauncher",
            "com.netease.cloudmusic",
            "com.tal.abctimelibrary",
            "com.qiyi.video.pad",
            "com.ihuman.imath",
            "com.ihuman.english",
            "com.miui.creation",
            "com.maxframing.mipad",
            "com.miui.password",
            "com.miui.passwords",
            "com.aliyun.tongyi",
            "com.xiaomi.gamecenter.sdk.service",
            "com.xiaomi.mis",
            "com.xiaomi.youpin",
            "com.xiaomi.tinygame",
            "com.miui.yellowpage",
            "com.xiaomi.shop",
            "com.miui.voiceassist",
            "com.miui.voiceassistProxy",
            "com.xiaomi.vipaccount",
            "com.miui.findmy",
            "com.android.quicksearchbox",
            "com.mipay.wallet",
            "com.mi.health",
            "cn.wps.moffice_eng",
            "com.unionpay.tsmservice.mi",
            "com.miui.miservice",
            "com.miui.player",
            "com.android.browser",
            "com.baidu.input_mi",
            "com.miui.bugreport",
            "com.iflytek.inputmethod.miui",
            "com.xiaomi.mibrain.speech",
            "com.xiaomi.payment",
            "com.sohu.inputmethod.sogou.xiaomi",
            "com.xiaomi.aiasst.vision",
            "com.miui.greenguard",
            "com.xiaomi.aiasst.service",
            "com.xiaomi.smarthome",
            "com.milink.service",
            "com.miui.contentcatcher",
            "com.xunlei.downloadprovider",
            "com.larus.nova",
            "com.hunantv.imgo.activity",
        ),
        *disable(
            "com.duokan.reader",
            "com.miui.video",
            "com.miui.newhome",
            "com.xiaomi.gamecenter",
            "com.miui.creation",
        ),
        Install("APK/1.CH_Play.apk"),
        Install("APK/Gallery_OS3.apk"),
        Push("APK/2.Gboard.apk"),
        Push("APK/3.Trinh_Duyet.apk"),
        Push("APK/4.SetEdit.apk"),
        Push("APK/DevCheck.apk"),
        Push("APK/Theme_Global.apk"),
        Push("APK/Gallery_OS3.apk"),
        Push("APK/Gallery_OS4.apk"),
        Push("APK/Zalo.apk"),
        Push("APK/Messenger.apk"),
        Push("APK/YouTube.apk"),
        IME_ENABLE,
        IME_SET,
        DEV_ON,
    ),
)

OPPO = Profile(
    id="oppo",
    name="OPPO / Realme / OnePlus",
    subtitle="ColorOS · realme UI · OxygenOS",
    brands=("oppo", "realme", "oneplus"),
    accent="#1BA672",
    steps=(
        *uninstall(
            "com.zhihu.android",
            "com.wuba",
            "cn.com.people.watch",
            "com.ximalaya.ting.android",
            "com.baidu.netdisk",
            "com.larus.nova",
            "com.sdu.didi.psnger",
            "com.aliyun.tongyi",
            "com.baidu.searchbox",
            "com.oplus.sos",
            "com.achievo.vipshop",
            "com.tencent.qqlive",
            "com.jingdong.app.mall",
            "com.sankuai.meituan",
            "com.nearme.fusionplay",
            "com.aiunit.aon",
            "com.oplus.ocar",
            "com.heytap.opluscarlink",
            "com.heytap.music",
            "com.alibaba.wireless",
            "com.taobao.idlefish",
            "com.unionpay.tsmservice",
            "com.finshell.wallet",
            "com.oplus.ovoicemanager.wakeup",
            "com.phoenix.read",
            "com.baidu.BaiduMap",
            "com.xs.fm",
            "com.dragon.read",
            "com.qiyi.video",
            "com.taobao.taobao",
            "com.eg.android.AlipayGphone",
            "ctrip.android.view",
            "com.ss.android.ugc.aweme",
            "com.oneplus.member",
            "com.xingin.xhs",
            "com.quark.browser",
            "tv.danmaku.bili",
            "com.tongcheng.android",
            "com.oplus.tips",
            "com.youku.phone",
            "com.oneplus.bbs",
            "com.oneplus.brickmode",
            "com.sina.weibo",
            "com.oplus.aiwriter",
            "com.heytap.yoli",
            "com.UCMobile",
            "com.oplus.aicall",
            "com.coloros.codebook",
            "com.ss.android.article.news",
            "com.sohu.inputmethod.sogouoem",
            "com.oplus.logkit",
            "com.xunmeng.pinduoduo",
            "com.redteamobile.roaming",
            "com.oppo.store",
            "com.heytap.health",
            "com.baidu.input_oppo",
            "com.heytap.speechassist",
            "com.oplus.aimemory",
            "com.coloros.colordirectservice",
            "com.coloros.childrenspace",
            "com.oplus.play",
            "com.smile.gifmaker",
            "com.coloros.familyguard",
            "com.coloros.digitalwellbeing",
            "com.coloros.shortcuts",
            "com.coloros.ocrscanner",
            "com.oplus.dmp",
            "com.coloros.accessibilityassistant",
            "com.dianping.v1",
            "com.oplus.member",
            "com.coloros.sceneservice",
            "com.autonavi.minimap",
            "com.realme.wellbeing",
            "com.realmecomm.app",
            "com.realme.storecn",
            "com.realme.linkcn",
            "com.heytap.member",
            "com.taobao.live",
            "com.yuemeng.speechsuite",
        ),
        *disable(
            "com.heytap.reader",
            "com.unionpay.tsmservice",
            "com.nearme.gamecenter",
            "com.oppo.community",
            "com.oplus.ovoicemanager.wakeup",
            "com.heytap.book",
            "com.oplus.aiwriter",
            "com.oplus.aicall",
            "com.oplus.dmp",
            "com.heytap.speechassist",
            "com.oplus.keyboard",
            "com.oplus.aimemory",
            "com.coloros.colordirectservice",
            "com.heytap.music",
            "com.heytap.yoli",
            "com.finshell.wallet",
        ),
        Install("APK/1.CH_Play.apk"),
        Install("APK/2.Gboard.apk"),
        IME_ENABLE,
        IME_SET,
        Install("APK/3.Trinh_Duyet.apk"),
        CHROME_DEFAULT,
        ZALO_SPLIT,
        FACEBOOK_SPLIT,
        Install("APK/Messenger.apk"),
        Install("APK/YouTube.apk"),
        Install("APK/DevCheck.apk"),
        DEV_OFF,
    ),
)

HONOR = Profile(
    id="honor",
    name="Honor / Huawei",
    subtitle="MagicOS · EMUI · HarmonyOS",
    brands=("honor", "huawei"),
    accent="#3D7BFF",
    steps=(
        *uninstall(
            "com.eg.android.AlipayGphone",
            "com.quark.browser",
            "com.UCMobile",
            "com.xunmeng.pinduoduo",
            "com.autonavi.minimap",
            "com.larus.nova",
            "com.tencent.hunyuan.app.chat",
            "com.smile.gifmaker",
            "com.alibaba.wireless",
            "com.aliyun.tongyi",
            "ctrip.android.view",
            "com.phoenix.read",
            "com.taobao.idlefish",
            "com.baidu.searchbox",
            "com.xs.fm",
            "com.dragon.read",
            "com.qiyi.video",
            "com.taobao.taobao",
            "com.ss.android.ugc.aweme",
            "com.xingin.xhs",
            "tv.danmaku.bili",
            "com.tongcheng.android",
            "com.sina.weibo",
            "com.ss.android.article.news",
            "com.dianping.v1",
            "com.baidu.BaiduMap",
            "cn.wps.moffice_eng",
            "com.hihonor.cloudmusic",
            "com.hihonor.dz.reader",
            "com.hihonor.youku.video",
            "com.tencent.qqlive",
            "com.baidu.netdisk",
            "com.hihonor.baidu.browser",
            "com.baidu.swan",
            "com.achievo.vipshop",
            "com.jingdong.app.mall",
            "com.hihonor.lens",
            "com.hihonor.magicvoice",
            "com.hihonor.voiceengine",
            "com.honor.quickgamecenter",
            "com.hihonor.tips",
            "com.hihonor.collectcenter",
            "com.hihonor.health",
            "cn.honor.qinxuan",
            "com.hihonor.brain",
            "com.hihonor.redteamobile.roaming",
            "com.hihonor.appmarket",
            "com.hihonor.magichome",
            "com.hihonor.sceneservice",
            "com.hihonor.vmall",
            "com.hihonor.popularapps",
            "com.sankuai.meituan",
            "com.hihonor.servicecenter",
            "com.hihonor.auto",
            "com.hihonor.devicefinder",
            "com.baidu.input_hihonor",
            "com.hihonor.search",
            "com.hihonor.hiboard",
            "com.hihonor.wallet",
            "com.honor.yoyoappsug",
            "com.honor.yoyocards",
            "com.hihonor.magazine",
            "com.hihonor.recordassistant",
            "com.hihonor.findmydevice",
            "com.zhihu.android",
            "com.sdu.didi.psnger",
            "com.sohu.inputmethod.sogou.honor",
            "com.Qunar",
            "com.honor.browser",
            "com.ximalaya.ting.android",
            "com.hpbr.bosszhipin",
            "com.hihonor.satellite",
            "com.huawei.wallet.facard",
            "com.huawei.ohos.videoeditor",
            "com.huafen.harmonyos_google",
            "com.huawei.hmos.himovie.fa",
            "com.vmall.client",
            "com.huawei.himovie",
            "com.huawei.hwread.dz",
            "com.huawei.wallet",
            "com.huawei.meetime",
            "com.huawei.hwvoipservice",
            "com.huawei.browser",
            "com.huawei.browser.fa",
            "com.huawei.smarthome",
            "com.huawei.ohos.smarthome",
            "com.huawei.hiskytone",
            "com.huawei.skytone",
            "com.huawei.android.tips",
            "com.huawei.health",
            "com.huawei.ohos.health",
            "com.huawei.educenter",
            "com.huawei.gamebox",
            "com.huawei.lives",
            "com.petal.litegames",
            "com.huawei.ohos.suggestion",
            "com.huawei.mycenter",
            "com.huawei.intelligent",
            "com.huawei.appmarket",
            "com.huawei.search",
            "com.hihonor.keychain",
        ),
        *disable(
            "com.hihonor.vmall",
            "com.hihonor.magichome",
            "com.hihonor.health",
            "com.hihonor.cloudmusic",
            "com.hihonor.youku.video",
            "com.hihonor.popularapps",
            "cn.honor.qinxuan",
            "com.hihonor.dz.reader",
            "com.hihonor.redteamobile.roaming",
            "com.hihonor.tips",
            "com.hihonor.servicecenter",
            "com.hihonor.auto",
            "com.hihonor.devicefinder",
            "com.honor.quickgamecenter",
            "com.hihonor.wallet",
            "com.hihonor.findmydevice",
            "com.hihonor.magictranslate",
            "com.huawei.ohos.inputmethod",
            "com.huawei.vassistant",
            "com.huawei.hifolder",
            "com.hihonor.gamecenter",
            "com.sohu.inputmethod.sogou.honor",
            "com.baidu.swan",
            "com.hihonor.collectcenter",
            "com.hihonor.magicvoice",
            "com.hihonor.voiceengine",
            "com.hihonor.lens",
            "com.baidu.input_hihonor",
            "com.hihonor.search",
            "com.hihonor.hiboard",
            "com.honor.browser",
            "com.hihonor.brain",
            "com.hihonor.recordassistant",
            "com.hihonor.remoteassist",
            "com.hihonor.edulauncher",
            "com.unionpay.tsmservice",
            "com.hihonor.quickgame",
        ),
        Install("APK/1.CH_Play.apk"),
        Install("APK/2.Gboard.apk"),
        IME_ENABLE,
        IME_SET,
        Install("APK/3.Trinh_Duyet.apk"),
        ZALO_SPLIT,
        FACEBOOK_SPLIT,
        Install("APK/Messenger.apk"),
        Install("APK/YouTube.apk"),
        Install("APK/DevCheck.apk"),
        DEV_OFF,
    ),
)

VIVO = Profile(
    id="vivo",
    name="vivo / iQOO",
    subtitle="OriginOS · Funtouch OS",
    brands=("vivo", "iqoo"),
    accent="#415FFF",
    note="Đăng nhập vivo trước",
    steps=(
        *uninstall(
            "com.UCMobile",
            "com.alibaba.wireless",
            "ctrip.android.view",
            "com.quark.browser",
            "com.phoenix.read",
            "com.taobao.idlefish",
            "com.unionpay.tsmservice",
            "com.vivo.wallet.appwidget",
            "com.larus.nova",
            "com.vivo.video.widget",
            "com.baidu.searchbox",
            "com.xs.fm",
            "com.dragon.read",
            "com.qiyi.video",
            "com.taobao.taobao",
            "cn.com.omronhealthcare.omronplus.vivo",
            "com.baidu.carlife.vivo",
            "com.eg.android.AlipayGphone",
            "com.ss.android.ugc.aweme",
            "com.vivo.ai.copilot.shortcut.component",
            "com.xingin.xhs",
            "com.xtc.originwidget",
            "tv.danmaku.bili",
            "com.aliyun.tongyi",
            "com.kaixinkan.ugc.video.atom",
            "com.chaozh.iReader",
            "com.jingdong.app.mall",
            "com.sina.weibo",
            "com.vivo.space",
            "com.kaixinkan.ugc.video",
            "com.vivo.ai.copilot",
            "com.vivo.launchercopilot",
            "com.smile.gifmaker",
            "com.xunmeng.pinduoduo",
            "com.sankuai.meituan",
            "com.baidu.input_vivo",
            "com.sohu.inputmethod.sogou.vivo",
            "com.ss.android.article.news",
            "com.vivo.translator.base",
            "com.vivo.translator",
            "com.android.VideoPlayer",
            "com.vivo.minigamecenter",
            "com.android.browser",
            "com.vivo.Tips",
            "com.bbk.iqoo.feedback",
            "com.vivo.puresearch",
            "com.vivo.sosappwidget",
            "com.vivo.browser.novel.widget",
            "com.vivo.smartLife",
            "com.vivo.vhome",
            "com.vivo.ai.base.copilot",
            "com.vivo.screenagent",
            "com.mobile.iroaming",
        ),
        *disable(
            "com.vivo.pie",
        ),
        Install("APK/1.CH_Play.apk"),
        Install("APK/2.Gboard.apk"),
        Install("APK/3.Trinh_Duyet.apk"),
        ZALO_SPLIT,
        FACEBOOK_SPLIT,
        Install("APK/Messenger.apk"),
        Install("APK/YouTube.apk"),
        Install("APK/DevCheck.apk"),
        DEV_OFF,
    ),
)

SONY = Profile(
    id="sony",
    name="Sony Xperia",
    subtitle="Máy Nhật · docomo · au · SoftBank",
    brands=("sony",),
    accent="#C9CDD6",
    note="Máy thị trường Nhật",
    steps=(
        *uninstall(
            "com.somc.sog03.onlinemanual",
            "com.sonymobile.xperia.guide",
            "com.sonymobile.xperia.cover",
            "com.sony.drbd.reader.other.jp",
            "com.felicanetworks.mfm.main",
            "com.gameloft.android.ANMP.GloftA9HM",
            "com.kddi.android.cmail",
            "com.activision.callofduty.shooter",
            "com.linkedin.android",
            "com.sonyericsson.androidapp.sehome",
            "jp.auone.wallet",
            "com.kddi.pass.launcher",
            "com.aura.oobe.kddi",
            "com.felicanetworks.mfs",
            "com.felicanetworks.mfw.a.boot",
            "jp.softbank.mb.plusmessage",
            "com.sony.playmemories.mobile",
            "com.sony.nfx.app.sfrc",
            "com.booking",
            "com.amazon.mShop.android.shopping",
            "com.amazon.avod.thirdpartyclient",
            "jp.co.sony.swish",
            "jp.softbank.mb.tdrl",
            "com.google.android.apps.youtube.music",
            "jp.softbank.beginnerguide",
            "jp.softbank.mb.bizlock",
            "jp.softbank.mb.datamigration",
            "jp.softbank.mb.parentalcontrols",
            "jp.co.yahoo.android.yjtop",
            "jp.softbank.mb.ichinaviclt",
            "com.sony.tvsideview.phone",
            "com.pubg.newstate",
            "com.scee.psxandroid",
            "jp.softbank.mb.securitypack",
            "com.sonypicturescore.xperia",
            "com.nttdocomo.android.msg",
            "com.nttdocomo.android.anshinsecurity",
            "com.nttdocomo.android.atf",
            "com.nttdocomo.android.idmanager",
            "com.nttdocomo.dcard",
            "com.nttdocomo.android.mymagazine",
            "com.rsupport.rs.activity.ntt",
            "com.tencent.qqspmi",
            "jp.dmapnavi.navi02",
            "jp.co.lawson.android",
            "jp.co.mcdonalds.android",
            "com.nttdocomo.android.cloudstorageservice",
            "com.nttdocomo.android.databackup",
            "com.nttdocomo.android.applicationmanager",
            "com.nttdocomo.android.applicationmanagersub",
            "com.nttdocomo.android.accountauthenticator",
            "com.nttdocomo.android.cloudset",
            "com.nttdocomo.android.sdcardbackup",
            "com.nttdocomo.android.initialization",
            "com.nttdocomo.android.dhome",
            "com.nextbit.app",
            "jp.co.nttdocomo.lcsapp",
            "jp.co.nttdocomo.carriermail",
            "com.android.contacts",
            "com.nttdocomo.android.docomoset",
            "com.nttdocomo.android.photocollection",
            "com.nttdocomo.android.dpoint",
            "com.nttdocomo.android.dmenu2",
            "com.nttdocomo.keitai.payment",
            "com.nttdocomo.android.voicetranslation",
            "com.nttdocomo.android.voiceeditor",
            "com.nttdocomo.android.mascot",
            "com.nttdocomo.android.mydocomo",
            "com.nttdocomo.android.networkservice",
            "com.nttdocomo.android.store",
            "jp.co.nttdocomo.saigaiban",
            "jp.co.omronsoft.android.decoemojimanager_docomo",
            "com.nttdocomo.android.devicehelp",
            "com.nttdocomo.android.schedulememo",
            "jp.co.disney.apps.gm.disneydx",
            "com.amazon.kindle",
            "com.somc.so51a.manual",
            "jp.id_credit_sp.android",
            "com.nttdocomo.android.phonemotion",
            "jp.co.sony.mc.so54c.manual",
            "com.nttdocomo.android.applicationmanagerrecommendshortcut",
            "com.nttdocomo.android.homezozo",
        ),
        *disable(
            "jp.softbank.mb.tdrl",
        ),
        Install("APK/Google_Messages.apk"),
    ),
)

PROFILES: tuple[Profile, ...] = (XIAOMI, OPPO, HONOR, VIVO, SONY)
PROFILE_BY_ID = {p.id: p for p in PROFILES}

GENERAL_NOTE = (
    "Cần bật chế độ nhà phát triển và bật gỡ lỗi USB, cắm cáp vào máy tính để chạy tool. "
    "Hệ thống sẽ xóa app rác, cài CH Play, bàn phím và trình duyệt vào thiết bị; riêng Xiaomi, "
    "các file APK sẽ nằm trong thư mục Download của ứng dụng Quản lý Tập tin (File Manager)."
)
CONNECT_STEP = "Cắm cáp vào máy tính → trên điện thoại bấm Cho phép (Allow) gỡ lỗi USB"

# Menu item 6 of the batch file: how to enable developer options + USB debugging, per brand.
GUIDES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Xiaomi / Redmi",
        (
            "Settings (Cài đặt)",
            "My Devices (Thiết bị của tôi)",
            "Nhấn liên tục 7 lần mục OS version (Phiên bản OS)",
            "Thoát ra, vào lại Settings (Cài đặt)",
            "Additional settings (Cài đặt bổ sung)",
            "Developer options (Tùy chọn cho nhà phát triển)",
            "Bật USB debugging (Gỡ lỗi qua USB)",
            CONNECT_STEP,
        ),
    ),
    (
        "OPPO / Realme / OnePlus",
        (
            "Cài đặt",
            "Giới thiệu về thiết bị",
            "Phiên bản",
            "Số phiên bản (nhấn liên tục 7 lần)",
            "Thoát ra, vào lại Cài đặt",
            "Hệ thống và cập nhật",
            "Tùy chọn nhà phát triển",
            "Gỡ lỗi qua USB (bật lên)",
            CONNECT_STEP,
        ),
    ),
    (
        "Honor / Huawei",
        (
            "Cài đặt",
            "Giới thiệu về điện thoại",
            "Số hiệu bản dựng (Honor) hoặc Phiên bản HarmonyOS (Huawei) — nhấn liên tục 7 lần",
            "Thoát ra, vào lại Cài đặt",
            "Hệ thống và cập nhật",
            "Tùy chọn nhà phát triển",
            "Gỡ lỗi USB (bật lên)",
            "Theo dõi ứng dụng do ADB cài (tắt đi)",
            CONNECT_STEP,
        ),
    ),
    (
        "vivo / iQOO",
        (
            "Đăng nhập tài khoản vivo trước khi chạy tool (bắt buộc)",
            "Cài đặt",
            "Giới thiệu về thiết bị",
            "Thông tin phiên bản",
            "Phiên bản phần mềm (nhấn liên tục 7 lần)",
            "Thoát ra, vào lại Cài đặt",
            "Quản lý và nâng cấp hệ thống",
            "Tùy chọn nhà phát triển (bật lên)",
            "Gỡ lỗi qua USB (bật lên)",
            CONNECT_STEP,
        ),
    ),
)


def to_batch_line(step: Step) -> str:
    """Render a step as the equivalent ``@ANDROID.bat`` command (used by the parity test and the log)."""
    if isinstance(step, Uninstall):
        return f"adb shell pm uninstall -k --user 0 {step.pkg}"
    if isinstance(step, Disable):
        return f"adb shell pm disable-user --user 0 {step.pkg}"
    if isinstance(step, Install):
        return f"adb install {step.apk}"
    if isinstance(step, InstallMulti):
        return "adb install-multiple " + " ".join(f'"{a}"' for a in step.apks)
    if isinstance(step, Push):
        return f"adb push {step.apk} {step.dest}"
    if isinstance(step, Shell):
        return f"adb shell {step.cmd}"
    raise TypeError(f"unknown step {step!r}")


def referenced_apks() -> set[str]:
    return {apk for profile in PROFILES for apk in profile.apks()}
