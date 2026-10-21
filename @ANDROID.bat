@shift /0
@shift /0
@shift /0
chcp 65001 > nul
:menu

@echo off
set rec_name=             VER 1.4 - 18/10/2026
set info=XÓA APP RÁC HỆ THỐNG - CÀI KHUNG DỊCH VỤ GOOGLE 
set contact=                    0899499444

title CHINA TOOL - DI ĐỘNG BULL
color 3f

cd /d "%~dp0"

:LOGO
CLS
ECHO.***********************************************
ECHO.%info%
ECHO.   PHIÊN BẢN: %rec_name%
ECHO.   LIÊN HỆ ZALO: %contact%
ECHO.Mua và bán điện thoại từ xa tại: DIDONGBULL.COM  
ECHO.***********************************************
ECHO.
ECHO.LƯU Ý: Cần bật chế độ nhà phát triển và bật gỡ lỗi USB, cắm cáp vào máy tính để chạy Tool. Hệ thống sẽ xóa app rác, cài đặt CH Play, bàn phím và trình duyệt vào thiết bị của bạn, riêng Xiaomi các tập tin APK sẽ nằm trong thư mục Download của ứng dụng Quản lý Tập tin (File Manager). Bạn vào Settings (Cài đặt) -^> Back up and restore (Sau lưu và khôi phục) -^> Mobile devices (Thiết bị di động) -^> Khôi phục tập tin -^> Thoát ra vào lại ứng dụng chủ đề chọn chủ đề có tiếng Việt.
ECHO.
ECHO.============ CHỌN THIẾT BỊ CỦA BẠN ============
ECHO.[1] Xiaomi, Redmi
ECHO.[2] Oppo, Realme, OnePlus
ECHO.[3] Honor, Huawei
ECHO.[4] Vivo, iQOO (đăng nhập tài khoản Vivo trước)
ECHO.[5] Sony Xperia (thị trường Nhật Bản, Japanese)
ECHO.[6] Xem hướng dẫn bật nhà phát triển gỡ lỗi USB
ECHO.[7] Fix lỗi máy tính không nhận diện điện thoại
ECHO.===============================================

set /p choice="NHẬP VÀO SỐ TƯƠNG ỨNG & BẤM ENTER ĐỂ CÀI ĐẶT: "

if "%choice%"=="1" goto cmd1
if "%choice%"=="2" goto cmd2
if "%choice%"=="3" goto cmd3
if "%choice%"=="4" goto cmd4
if "%choice%"=="5" goto cmd5
if "%choice%"=="6" goto cmd6
if "%choice%"=="7" goto cmd7

echo Lựa chọn không hợp lệ, vui lòng chọn lại!
pause
goto menu

:cmd1
ECHO.=============== XIAOMI / REDMI ================
ECHO................. Đang cài đặt .................
adb shell pm uninstall -k --user 0 com.miui.fm
adb shell pm uninstall -k --user 0 com.ximalaya.ting.android
adb shell pm uninstall -k --user 0 com.baidu.BaiduMap
adb shell pm uninstall -k --user 0 com.ss.android.auto
adb shell pm uninstall -k --user 0 com.fenxiang.storyline
adb shell pm uninstall -k --user 0 com.tencent.qqlive
adb shell pm uninstall -k --user 0 com.jingdong.app.mall
adb shell pm uninstall -k --user 0 ctrip.android.view
adb shell pm uninstall -k --user 0 com.autonavi.minimap
adb shell pm uninstall -k --user 0 com.achievo.vipshop
adb shell pm uninstall -k --user 0 com.sdu.didi.psnger
adb shell pm uninstall -k --user 0 com.alibaba.wireless
adb shell pm uninstall -k --user 0 com.zhihu.android
adb shell pm uninstall -k --user 0 com.UCMobile
adb shell pm uninstall -k --user 0 com.dianping.v1
adb shell pm uninstall -k --user 0 com.qiyi.video
adb shell pm uninstall -k --user 0 com.xiaomi.aireco
adb shell pm uninstall -k --user 0 com.xiaomi.aiservice
adb shell pm uninstall -k --user 0 com.taobao.idlefish
adb shell pm uninstall -k --user 0 com.phoenix.read
adb shell pm uninstall -k --user 0 com.xs.fm
adb shell pm uninstall -k --user 0 com.dragon.read
adb shell pm uninstall -k --user 0 com.taobao.taobao
adb shell pm uninstall -k --user 0 com.ss.android.ugc.aweme
adb shell pm uninstall -k --user 0 com.xingin.xhs
adb shell pm uninstall -k --user 0 com.xiaomi.minigame
adb shell pm uninstall -k --user 0 com.quark.browser
adb shell pm uninstall -k --user 0 tv.danmaku.bili
adb shell pm uninstall -k --user 0 com.tongcheng.android
adb shell pm uninstall -k --user 0 com.xiaomi.xmsf
adb shell pm uninstall -k --user 0 com.sina.weibo
adb shell pm uninstall -k --user 0 com.sankuai.meituan
adb shell pm uninstall -k --user 0 com.smile.gifmaker
adb shell pm uninstall -k --user 0 com.xunmeng.pinduoduo
adb shell pm uninstall -k --user 0 com.baidu.searchbox
adb shell pm uninstall -k --user 0 com.ss.android.article.news
adb shell pm uninstall -k --user 0 com.eg.android.AlipayGphone
adb shell pm uninstall -k --user 0 net.huanci.hsjpro
adb shell pm uninstall -k --user 0 com.xiaomi.wpslauncher
adb shell pm uninstall -k --user 0 com.hongen.app.word
adb shell pm uninstall -k --user 0 com.ihuman.pinyin
adb shell pm uninstall -k --user 0 com.xiaomi.kidspace
adb shell pm uninstall -k --user 0 com.xiaomi.cajlauncher
adb shell pm uninstall -k --user 0 com.netease.cloudmusic
adb shell pm uninstall -k --user 0 com.tal.abctimelibrary
adb shell pm uninstall -k --user 0 com.qiyi.video.pad
adb shell pm uninstall -k --user 0 com.ihuman.imath
adb shell pm uninstall -k --user 0 com.ihuman.english
adb shell pm uninstall -k --user 0 com.miui.creation
adb shell pm uninstall -k --user 0 com.maxframing.mipad
adb shell pm uninstall -k --user 0 com.miui.password
adb shell pm uninstall -k --user 0 com.miui.passwords
adb shell pm uninstall -k --user 0 com.aliyun.tongyi
adb shell pm uninstall -k --user 0 com.xiaomi.gamecenter.sdk.service
adb shell pm uninstall -k --user 0 com.xiaomi.mis
adb shell pm uninstall -k --user 0 com.xiaomi.youpin
adb shell pm uninstall -k --user 0 com.xiaomi.tinygame
adb shell pm uninstall -k --user 0 com.miui.yellowpage
adb shell pm uninstall -k --user 0 com.xiaomi.shop
adb shell pm uninstall -k --user 0 com.miui.voiceassist
adb shell pm uninstall -k --user 0 com.miui.voiceassistProxy
adb shell pm uninstall -k --user 0 com.xiaomi.vipaccount
adb shell pm uninstall -k --user 0 com.miui.findmy
adb shell pm uninstall -k --user 0 com.android.quicksearchbox
adb shell pm uninstall -k --user 0 com.mipay.wallet
adb shell pm uninstall -k --user 0 com.mi.health
adb shell pm uninstall -k --user 0 cn.wps.moffice_eng
adb shell pm uninstall -k --user 0 com.unionpay.tsmservice.mi
adb shell pm uninstall -k --user 0 com.miui.miservice
adb shell pm uninstall -k --user 0 com.miui.player
adb shell pm uninstall -k --user 0 com.android.browser
adb shell pm uninstall -k --user 0 com.baidu.input_mi
adb shell pm uninstall -k --user 0 com.miui.bugreport
adb shell pm uninstall -k --user 0 com.iflytek.inputmethod.miui
adb shell pm uninstall -k --user 0 com.xiaomi.mibrain.speech
adb shell pm uninstall -k --user 0 com.xiaomi.payment
adb shell pm uninstall -k --user 0 com.sohu.inputmethod.sogou.xiaomi
adb shell pm uninstall -k --user 0 com.xiaomi.aiasst.vision
adb shell pm uninstall -k --user 0 com.miui.greenguard
adb shell pm uninstall -k --user 0 com.xiaomi.aiasst.service
adb shell pm uninstall -k --user 0 com.xiaomi.smarthome
adb shell pm uninstall -k --user 0 com.milink.service
adb shell pm uninstall -k --user 0 com.miui.contentcatcher
adb shell pm uninstall -k --user 0 com.xunlei.downloadprovider
adb shell pm uninstall -k --user 0 com.larus.nova
adb shell pm uninstall -k --user 0 com.hunantv.imgo.activity
adb shell pm disable-user --user 0 com.duokan.reader
adb shell pm disable-user --user 0 com.miui.video
adb shell pm disable-user --user 0 com.miui.newhome
adb shell pm disable-user --user 0 com.xiaomi.gamecenter
adb shell pm disable-user --user 0 com.miui.creation
adb install APK/1.CH_Play.apk
adb install APK/Gallery_OS3.apk
adb push APK/2.Gboard.apk /sdcard/download
adb push APK/3.Trinh_Duyet.apk /sdcard/download
adb push APK/4.SetEdit.apk /sdcard/download
adb push APK/DevCheck.apk /sdcard/download
adb push APK/Theme_Global.apk /sdcard/download
adb push APK/Gallery_OS3.apk /sdcard/download
adb push APK/Gallery_OS4.apk /sdcard/download
adb push APK/Zalo.apk /sdcard/download
adb push APK/Messenger.apk /sdcard/download
adb push APK/YouTube.apk /sdcard/download
adb shell ime enable com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME
adb shell ime set com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME
adb shell "settings put global development_settings_enabled 1 && settings put global adb_enabled 1"
echo Clearer
echo.
exit

:cmd2
ECHO.=========== OPPO / REALME / ONEPLUS ===========
ECHO................. Đang cài đặt .................
adb shell pm uninstall -k --user 0 com.zhihu.android
adb shell pm uninstall -k --user 0 com.wuba
adb shell pm uninstall -k --user 0 cn.com.people.watch
adb shell pm uninstall -k --user 0 com.ximalaya.ting.android
adb shell pm uninstall -k --user 0 com.baidu.netdisk
adb shell pm uninstall -k --user 0 com.larus.nova
adb shell pm uninstall -k --user 0 com.sdu.didi.psnger
adb shell pm uninstall -k --user 0 com.aliyun.tongyi 
adb shell pm uninstall -k --user 0 com.baidu.searchbox
adb shell pm uninstall -k --user 0 com.oplus.sos
adb shell pm uninstall -k --user 0 com.achievo.vipshop
adb shell pm uninstall -k --user 0 com.tencent.qqlive
adb shell pm uninstall -k --user 0 com.jingdong.app.mall
adb shell pm uninstall -k --user 0 com.sankuai.meituan
adb shell pm uninstall -k --user 0 com.nearme.fusionplay
adb shell pm uninstall -k --user 0 com.aiunit.aon
adb shell pm uninstall -k --user 0 com.oplus.ocar
adb shell pm uninstall -k --user 0 com.heytap.opluscarlink
adb shell pm uninstall -k --user 0 com.heytap.music
adb shell pm uninstall -k --user 0 com.alibaba.wireless
adb shell pm uninstall -k --user 0 com.taobao.idlefish
adb shell pm uninstall -k --user 0 com.unionpay.tsmservice
adb shell pm uninstall -k --user 0 com.finshell.wallet
adb shell pm uninstall -k --user 0 com.oplus.ovoicemanager.wakeup
adb shell pm uninstall -k --user 0 com.phoenix.read
adb shell pm uninstall -k --user 0 com.baidu.BaiduMap
adb shell pm uninstall -k --user 0 com.baidu.searchbox
adb shell pm uninstall -k --user 0 com.xs.fm
adb shell pm uninstall -k --user 0 com.dragon.read
adb shell pm uninstall -k --user 0 com.qiyi.video
adb shell pm uninstall -k --user 0 com.taobao.taobao
adb shell pm uninstall -k --user 0 com.eg.android.AlipayGphone
adb shell pm uninstall -k --user 0 ctrip.android.view
adb shell pm uninstall -k --user 0 com.ss.android.ugc.aweme
adb shell pm uninstall -k --user 0 com.oneplus.member
adb shell pm uninstall -k --user 0 com.xingin.xhs
adb shell pm uninstall -k --user 0 com.quark.browser
adb shell pm uninstall -k --user 0 tv.danmaku.bili
adb shell pm uninstall -k --user 0 com.tongcheng.android
adb shell pm uninstall -k --user 0 com.oplus.tips
adb shell pm uninstall -k --user 0 com.youku.phone
adb shell pm uninstall -k --user 0 com.oneplus.bbs
adb shell pm uninstall -k --user 0 com.oneplus.brickmode
adb shell pm uninstall -k --user 0 com.sina.weibo
adb shell pm uninstall -k --user 0 com.oplus.aiwriter
adb shell pm uninstall -k --user 0 com.heytap.yoli
adb shell pm uninstall -k --user 0 com.UCMobile
adb shell pm uninstall -k --user 0 com.oplus.aicall
adb shell pm uninstall -k --user 0 com.coloros.codebook
adb shell pm uninstall -k --user 0 com.ss.android.article.news
adb shell pm uninstall -k --user 0 com.sohu.inputmethod.sogouoem
adb shell pm uninstall -k --user 0 com.oplus.logkit
adb shell pm uninstall -k --user 0 com.xunmeng.pinduoduo
adb shell pm uninstall -k --user 0 com.redteamobile.roaming
adb shell pm uninstall -k --user 0 com.oppo.store
adb shell pm uninstall -k --user 0 com.heytap.health
adb shell pm uninstall -k --user 0 com.baidu.input_oppo
adb shell pm uninstall -k --user 0 com.heytap.speechassist
adb shell pm uninstall -k --user 0 com.oplus.aimemory
adb shell pm uninstall -k --user 0 com.coloros.colordirectservice
adb shell pm uninstall -k --user 0 com.coloros.childrenspace
adb shell pm uninstall -k --user 0 com.oplus.play
adb shell pm uninstall -k --user 0 com.smile.gifmaker
adb shell pm uninstall -k --user 0 com.coloros.familyguard
adb shell pm uninstall -k --user 0 com.coloros.digitalwellbeing
adb shell pm uninstall -k --user 0 com.coloros.shortcuts
adb shell pm uninstall -k --user 0 com.coloros.ocrscanner
adb shell pm uninstall -k --user 0 com.oplus.dmp
adb shell pm uninstall -k --user 0 com.coloros.accessibilityassistant
adb shell pm uninstall -k --user 0 com.dianping.v1
adb shell pm uninstall -k --user 0 com.oplus.member
adb shell pm uninstall -k --user 0 com.coloros.sceneservice
adb shell pm uninstall -k --user 0 com.autonavi.minimap
adb shell pm uninstall -k --user 0 com.realme.wellbeing
adb shell pm uninstall -k --user 0 com.realmecomm.app
adb shell pm uninstall -k --user 0 com.realme.storecn
adb shell pm uninstall -k --user 0 com.realme.linkcn
adb shell pm uninstall -k --user 0 com.heytap.member
adb shell pm uninstall -k --user 0 com.taobao.live
adb shell pm uninstall -k --user 0 com.yuemeng.speechsuite 
adb shell pm disable-user --user 0 com.heytap.reader
adb shell pm disable-user --user 0 com.unionpay.tsmservice
adb shell pm disable-user --user 0 com.nearme.gamecenter
adb shell pm disable-user --user 0 com.oppo.community
adb shell pm disable-user --user 0 com.oplus.ovoicemanager.wakeup
adb shell pm disable-user --user 0 com.heytap.book
adb shell pm disable-user --user 0 com.oplus.aiwriter
adb shell pm disable-user --user 0 com.oplus.aicall
adb shell pm disable-user --user 0 com.oplus.dmp
adb shell pm disable-user --user 0 com.heytap.speechassist
adb shell pm disable-user --user 0 com.oplus.keyboard
adb shell pm disable-user --user 0 com.oplus.aimemory
adb shell pm disable-user --user 0 com.coloros.colordirectservice
adb shell pm disable-user --user 0 com.heytap.music
adb shell pm disable-user --user 0 com.heytap.yoli
adb shell pm disable-user --user 0 com.finshell.wallet
adb install APK/1.CH_Play.apk
adb install APK/2.Gboard.apk
adb shell ime enable com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME
adb shell ime set com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME
adb install APK/3.Trinh_Duyet.apk
adb shell cmd role add-role-holder --user 0 android.app.role.BROWSER com.android.chrome
adb install-multiple "APK/Zalo/com.zing.zalo.apk" "APK/Zalo/config.arm64_v8a.apk" "APK/Zalo/config.hdpi.apk"
adb install-multiple "APK/Facebook/com.facebook.katana.apk" "APK/Facebook/config.xxhdpi.apk"
adb install APK/Messenger.apk
adb install APK/YouTube.apk
adb install APK/DevCheck.apk
adb shell "settings put global development_settings_enabled 0 && settings put global adb_enabled 0"
echo Clearer
echo.
exit

:cmd3
ECHO.=============== HONOR / HUAWEI ================
ECHO................. Đang cài đặt .................
adb shell pm uninstall -k --user 0 com.eg.android.AlipayGphone
adb shell pm uninstall -k --user 0 com.quark.browser
adb shell pm uninstall -k --user 0 com.UCMobile
adb shell pm uninstall -k --user 0 com.xunmeng.pinduoduo
adb shell pm uninstall -k --user 0 com.autonavi.minimap
adb shell pm uninstall -k --user 0 com.larus.nova
adb shell pm uninstall -k --user 0 com.tencent.hunyuan.app.chat
adb shell pm uninstall -k --user 0 com.smile.gifmaker
adb shell pm uninstall -k --user 0 com.alibaba.wireless
adb shell pm uninstall -k --user 0 com.aliyun.tongyi
adb shell pm uninstall -k --user 0 ctrip.android.view
adb shell pm uninstall -k --user 0 com.phoenix.read
adb shell pm uninstall -k --user 0 com.taobao.idlefish
adb shell pm uninstall -k --user 0 com.baidu.searchbox
adb shell pm uninstall -k --user 0 com.xs.fm
adb shell pm uninstall -k --user 0 com.dragon.read
adb shell pm uninstall -k --user 0 com.qiyi.video
adb shell pm uninstall -k --user 0 com.taobao.taobao
adb shell pm uninstall -k --user 0 com.ss.android.ugc.aweme
adb shell pm uninstall -k --user 0 com.xingin.xhs
adb shell pm uninstall -k --user 0 tv.danmaku.bili
adb shell pm uninstall -k --user 0 com.tongcheng.android
adb shell pm uninstall -k --user 0 com.sina.weibo
adb shell pm uninstall -k --user 0 com.ss.android.article.news
adb shell pm uninstall -k --user 0 com.dianping.v1
adb shell pm uninstall -k --user 0 com.baidu.BaiduMap
adb shell pm uninstall -k --user 0 cn.wps.moffice_eng
adb shell pm uninstall -k --user 0 com.hihonor.cloudmusic
adb shell pm uninstall -k --user 0 com.hihonor.dz.reader
adb shell pm uninstall -k --user 0 com.hihonor.youku.video
adb shell pm uninstall -k --user 0 com.tencent.qqlive
adb shell pm uninstall -k --user 0 com.baidu.netdisk
adb shell pm uninstall -k --user 0 com.hihonor.baidu.browser
adb shell pm uninstall -k --user 0 com.baidu.swan
adb shell pm uninstall -k --user 0 com.achievo.vipshop
adb shell pm uninstall -k --user 0 com.jingdong.app.mall
adb shell pm uninstall -k --user 0 com.hihonor.lens
adb shell pm uninstall -k --user 0 com.hihonor.magicvoice
adb shell pm uninstall -k --user 0 com.hihonor.voiceengine
adb shell pm uninstall -k --user 0 com.honor.quickgamecenter
adb shell pm uninstall -k --user 0 com.hihonor.tips
adb shell pm uninstall -k --user 0 com.hihonor.collectcenter
adb shell pm uninstall -k --user 0 com.hihonor.health
adb shell pm uninstall -k --user 0 cn.honor.qinxuan
adb shell pm uninstall -k --user 0 com.hihonor.brain
adb shell pm uninstall -k --user 0 com.hihonor.redteamobile.roaming
adb shell pm uninstall -k --user 0 com.hihonor.appmarket
adb shell pm uninstall -k --user 0 com.hihonor.magichome
adb shell pm uninstall -k --user 0 com.hihonor.sceneservice
adb shell pm uninstall -k --user 0 com.hihonor.vmall
adb shell pm uninstall -k --user 0 com.hihonor.popularapps
adb shell pm uninstall -k --user 0 com.sankuai.meituan
adb shell pm uninstall -k --user 0 com.hihonor.servicecenter
adb shell pm uninstall -k --user 0 com.hihonor.auto
adb shell pm uninstall -k --user 0 com.hihonor.devicefinder
adb shell pm uninstall -k --user 0 com.baidu.input_hihonor
adb shell pm uninstall -k --user 0 com.hihonor.search
adb shell pm uninstall -k --user 0 com.hihonor.hiboard
adb shell pm uninstall -k --user 0 com.hihonor.wallet
adb shell pm uninstall -k --user 0 com.honor.yoyoappsug
adb shell pm uninstall -k --user 0 com.honor.yoyocards
adb shell pm uninstall -k --user 0 com.hihonor.magazine
adb shell pm uninstall -k --user 0 com.hihonor.recordassistant
adb shell pm uninstall -k --user 0 com.hihonor.findmydevice
adb shell pm uninstall -k --user 0 com.zhihu.android
adb shell pm uninstall -k --user 0 com.sdu.didi.psnger
adb shell pm uninstall -k --user 0 com.sohu.inputmethod.sogou.honor
adb shell pm uninstall -k --user 0 com.Qunar
adb shell pm uninstall -k --user 0 com.honor.browser
adb shell pm uninstall -k --user 0 com.ximalaya.ting.android
adb shell pm uninstall -k --user 0 com.hpbr.bosszhipin
adb shell pm uninstall -k --user 0 com.hihonor.satellite
adb shell pm uninstall -k --user 0 com.huawei.wallet.facard
adb shell pm uninstall -k --user 0 com.huawei.ohos.videoeditor
adb shell pm uninstall -k --user 0 com.huafen.harmonyos_google
adb shell pm uninstall -k --user 0 com.huawei.hmos.himovie.fa
adb shell pm uninstall -k --user 0 com.vmall.client
adb shell pm uninstall -k --user 0 com.huawei.himovie
adb shell pm uninstall -k --user 0 com.huawei.hwread.dz
adb shell pm uninstall -k --user 0 com.huawei.wallet
adb shell pm uninstall -k --user 0 com.huawei.meetime
adb shell pm uninstall -k --user 0 com.huawei.hwvoipservice
adb shell pm uninstall -k --user 0 com.huawei.browser
adb shell pm uninstall -k --user 0 com.huawei.browser.fa
adb shell pm uninstall -k --user 0 com.huawei.smarthome
adb shell pm uninstall -k --user 0 com.huawei.ohos.smarthome
adb shell pm uninstall -k --user 0 com.huawei.hiskytone
adb shell pm uninstall -k --user 0 com.huawei.skytone
adb shell pm uninstall -k --user 0 com.huawei.android.tips
adb shell pm uninstall -k --user 0 com.huawei.health
adb shell pm uninstall -k --user 0 com.huawei.ohos.health
adb shell pm uninstall -k --user 0 com.huawei.educenter
adb shell pm uninstall -k --user 0 com.huawei.gamebox
adb shell pm uninstall -k --user 0 com.huawei.lives
adb shell pm uninstall -k --user 0 com.petal.litegames
adb shell pm uninstall -k --user 0 com.huawei.ohos.suggestion
adb shell pm uninstall -k --user 0 com.huawei.mycenter
adb shell pm uninstall -k --user 0 com.huawei.intelligent
adb shell pm uninstall -k --user 0 com.huawei.appmarket
adb shell pm uninstall -k --user 0 com.huawei.search
adb shell pm uninstall -k --user 0 com.hihonor.keychain
adb shell pm disable-user --user 0 com.hihonor.vmall
adb shell pm disable-user --user 0 com.hihonor.magichome
adb shell pm disable-user --user 0 com.hihonor.health
adb shell pm disable-user --user 0 com.hihonor.cloudmusic
adb shell pm disable-user --user 0 com.hihonor.youku.video
adb shell pm disable-user --user 0 com.hihonor.popularapps
adb shell pm disable-user --user 0 cn.honor.qinxuan
adb shell pm disable-user --user 0 com.hihonor.dz.reader
adb shell pm disable-user --user 0 com.hihonor.redteamobile.roaming
adb shell pm disable-user --user 0 com.hihonor.tips
adb shell pm disable-user --user 0 com.hihonor.servicecenter
adb shell pm disable-user --user 0 com.hihonor.auto
adb shell pm disable-user --user 0 com.hihonor.devicefinder
adb shell pm disable-user --user 0 com.honor.quickgamecenter
adb shell pm disable-user --user 0 com.hihonor.wallet
adb shell pm disable-user --user 0 com.hihonor.findmydevice
adb shell pm disable-user --user 0 com.hihonor.magictranslate
adb shell pm disable-user --user 0 com.huawei.ohos.inputmethod
adb shell pm disable-user --user 0 com.huawei.vassistant
adb shell pm disable-user --user 0 com.huawei.hifolder
adb shell pm disable-user --user 0 com.hihonor.gamecenter
adb shell pm disable-user --user 0 com.sohu.inputmethod.sogou.honor
adb shell pm disable-user --user 0 com.baidu.swan
adb shell pm disable-user --user 0 com.hihonor.collectcenter
adb shell pm disable-user --user 0 com.hihonor.magicvoice
adb shell pm disable-user --user 0 com.hihonor.voiceengine
adb shell pm disable-user --user 0 com.hihonor.lens
adb shell pm disable-user --user 0 com.baidu.input_hihonor
adb shell pm disable-user --user 0 com.hihonor.search
adb shell pm disable-user --user 0 com.hihonor.hiboard
adb shell pm disable-user --user 0 com.honor.browser
adb shell pm disable-user --user 0 com.hihonor.brain
adb shell pm disable-user --user 0 com.hihonor.recordassistant
adb shell pm disable-user --user 0 com.hihonor.remoteassist
adb shell pm disable-user --user 0 com.hihonor.edulauncher
adb shell pm disable-user --user 0 com.unionpay.tsmservice
adb shell pm disable-user --user 0 com.hihonor.quickgame
adb install APK/1.CH_Play.apk
adb install APK/2.Gboard.apk
adb shell ime enable com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME
adb shell ime set com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME
adb install APK/3.Trinh_Duyet.apk
adb install-multiple "APK/Zalo/com.zing.zalo.apk" "APK/Zalo/config.arm64_v8a.apk" "APK/Zalo/config.hdpi.apk"
adb install-multiple "APK/Facebook/com.facebook.katana.apk" "APK/Facebook/config.xxhdpi.apk"
adb install APK/Messenger.apk
adb install APK/YouTube.apk
adb install APK/DevCheck.apk
adb shell "settings put global development_settings_enabled 0 && settings put global adb_enabled 0"
echo Clearer
echo.
exit

:cmd4
ECHO.================= VIVO / IQOO =================
ECHO.................. Đang cài đặt ................
adb shell pm uninstall -k --user 0 com.UCMobile
adb shell pm uninstall -k --user 0 com.alibaba.wireless
adb shell pm uninstall -k --user 0 ctrip.android.view
adb shell pm uninstall -k --user 0 com.quark.browser
adb shell pm uninstall -k --user 0 com.phoenix.read
adb shell pm uninstall -k --user 0 com.taobao.idlefish
adb shell pm uninstall -k --user 0 com.unionpay.tsmservice
adb shell pm uninstall -k --user 0 com.vivo.wallet.appwidget
adb shell pm uninstall -k --user 0 com.larus.nova
adb shell pm uninstall -k --user 0 com.vivo.video.widget
adb shell pm uninstall -k --user 0 com.baidu.searchbox
adb shell pm uninstall -k --user 0 com.xs.fm
adb shell pm uninstall -k --user 0 com.dragon.read
adb shell pm uninstall -k --user 0 com.qiyi.video
adb shell pm uninstall -k --user 0 com.taobao.taobao
adb shell pm uninstall -k --user 0 cn.com.omronhealthcare.omronplus.vivo
adb shell pm uninstall -k --user 0 com.baidu.carlife.vivo
adb shell pm uninstall -k --user 0 com.eg.android.AlipayGphone
adb shell pm uninstall -k --user 0 com.ss.android.ugc.aweme
adb shell pm uninstall -k --user 0 com.vivo.ai.copilot.shortcut.component
adb shell pm uninstall -k --user 0 com.xingin.xhs
adb shell pm uninstall -k --user 0 com.xtc.originwidget
adb shell pm uninstall -k --user 0 tv.danmaku.bili
adb shell pm uninstall -k --user 0 com.aliyun.tongyi
adb shell pm uninstall -k --user 0 com.kaixinkan.ugc.video.atom
adb shell pm uninstall -k --user 0 com.chaozh.iReader
adb shell pm uninstall -k --user 0 com.jingdong.app.mall
adb shell pm uninstall -k --user 0 com.sina.weibo
adb shell pm uninstall -k --user 0 com.vivo.space
adb shell pm uninstall -k --user 0 com.kaixinkan.ugc.video
adb shell pm uninstall -k --user 0 com.vivo.ai.copilot
adb shell pm uninstall -k --user 0 com.vivo.launchercopilot
adb shell pm uninstall -k --user 0 com.smile.gifmaker
adb shell pm uninstall -k --user 0 com.xunmeng.pinduoduo
adb shell pm uninstall -k --user 0 com.sankuai.meituan
adb shell pm uninstall -k --user 0 com.baidu.input_vivo
adb shell pm uninstall -k --user 0 com.sohu.inputmethod.sogou.vivo
adb shell pm uninstall -k --user 0 com.ss.android.article.news
adb shell pm uninstall -k --user 0 com.vivo.translator.base
adb shell pm uninstall -k --user 0 com.vivo.translator
adb shell pm uninstall -k --user 0 com.android.VideoPlayer
adb shell pm uninstall -k --user 0 com.vivo.minigamecenter
adb shell pm uninstall -k --user 0 com.android.browser
adb shell pm uninstall -k --user 0 com.vivo.Tips
adb shell pm uninstall -k --user 0 com.bbk.iqoo.feedback
adb shell pm uninstall -k --user 0 com.vivo.puresearch
adb shell pm uninstall -k --user 0 com.vivo.sosappwidget
adb shell pm uninstall -k --user 0 com.vivo.browser.novel.widget
adb shell pm uninstall -k --user 0 com.vivo.smartLife
adb shell pm uninstall -k --user 0 com.vivo.vhome
adb shell pm uninstall -k --user 0 com.vivo.ai.base.copilot
adb shell pm uninstall -k --user 0 com.vivo.screenagent
adb shell pm uninstall -k --user 0 com.mobile.iroaming
adb shell pm disable-user --user 0 com.vivo.pie
adb install APK/1.CH_Play.apk
adb install APK/2.Gboard.apk
adb install APK/3.Trinh_Duyet.apk
adb install-multiple "APK/Zalo/com.zing.zalo.apk" "APK/Zalo/config.arm64_v8a.apk" "APK/Zalo/config.hdpi.apk"
adb install-multiple "APK/Facebook/com.facebook.katana.apk" "APK/Facebook/config.xxhdpi.apk"
adb install APK/Messenger.apk
adb install APK/YouTube.apk
adb install APK/DevCheck.apk
adb shell "settings put global development_settings_enabled 0 && settings put global adb_enabled 0"
echo Clearer
echo.
exit

:cmd5
ECHO.================= SONY XPERIA =================
ECHO.................. Đang cài đặt ................
adb shell pm uninstall -k --user 0 com.somc.sog03.onlinemanual
adb shell pm uninstall -k --user 0 com.sonymobile.xperia.guide
adb shell pm uninstall -k --user 0 com.sonymobile.xperia.cover
adb shell pm uninstall -k --user 0 com.sony.drbd.reader.other.jp
adb shell pm uninstall -k --user 0 com.felicanetworks.mfm.main
adb shell pm uninstall -k --user 0 com.gameloft.android.ANMP.GloftA9HM
adb shell pm uninstall -k --user 0 com.kddi.android.cmail
adb shell pm uninstall -k --user 0 com.activision.callofduty.shooter
adb shell pm uninstall -k --user 0 com.linkedin.android
adb shell pm uninstall -k --user 0 com.sonyericsson.androidapp.sehome
adb shell pm uninstall -k --user 0 jp.auone.wallet
adb shell pm uninstall -k --user 0 com.kddi.pass.launcher
adb shell pm uninstall -k --user 0 com.aura.oobe.kddi
adb shell pm uninstall -k --user 0 com.felicanetworks.mfs
adb shell pm uninstall -k --user 0 com.felicanetworks.mfw.a.boot
adb shell pm uninstall -k --user 0 jp.softbank.mb.plusmessage
adb shell pm uninstall -k --user 0 com.sony.playmemories.mobile
adb shell pm uninstall -k --user 0 com.sony.nfx.app.sfrc
adb shell pm uninstall -k --user 0 com.booking
adb shell pm uninstall -k --user 0 com.amazon.mShop.android.shopping
adb shell pm uninstall -k --user 0 com.amazon.avod.thirdpartyclient
adb shell pm uninstall -k --user 0 jp.co.sony.swish
adb shell pm uninstall -k --user 0 jp.softbank.mb.tdrl
adb shell pm uninstall -k --user 0 com.google.android.apps.youtube.music
adb shell pm uninstall -k --user 0 jp.softbank.beginnerguide
adb shell pm uninstall -k --user 0 jp.softbank.mb.bizlock
adb shell pm uninstall -k --user 0 jp.softbank.mb.datamigration
adb shell pm uninstall -k --user 0 jp.softbank.mb.parentalcontrols
adb shell pm uninstall -k --user 0 jp.co.yahoo.android.yjtop
adb shell pm uninstall -k --user 0 jp.softbank.mb.tdrl
adb shell pm uninstall -k --user 0 jp.softbank.mb.ichinaviclt
adb shell pm uninstall -k --user 0 com.sony.tvsideview.phone
adb shell pm uninstall -k --user 0 com.pubg.newstate
adb shell pm uninstall -k --user 0 com.scee.psxandroid
adb shell pm uninstall -k --user 0 jp.softbank.mb.securitypack
adb shell pm uninstall -k --user 0 com.sonypicturescore.xperia
adb shell pm uninstall -k --user 0 com.nttdocomo.android.msg
adb shell pm uninstall -k --user 0 com.nttdocomo.android.anshinsecurity
adb shell pm uninstall -k --user 0 com.nttdocomo.android.atf
adb shell pm uninstall -k --user 0 com.nttdocomo.android.idmanager
adb shell pm uninstall -k --user 0 com.nttdocomo.dcard
adb shell pm uninstall -k --user 0 com.nttdocomo.android.mymagazine
adb shell pm uninstall -k --user 0 com.rsupport.rs.activity.ntt
adb shell pm uninstall -k --user 0 com.tencent.qqspmi
adb shell pm uninstall -k --user 0 jp.dmapnavi.navi02
adb shell pm uninstall -k --user 0 jp.co.lawson.android
adb shell pm uninstall -k --user 0 jp.co.mcdonalds.android
adb shell pm uninstall -k --user 0 com.nttdocomo.android.cloudstorageservice
adb shell pm uninstall -k --user 0 com.nttdocomo.android.databackup
adb shell pm uninstall -k --user 0 com.nttdocomo.android.applicationmanager
adb shell pm uninstall -k --user 0 com.nttdocomo.android.applicationmanagersub
adb shell pm uninstall -k --user 0 com.nttdocomo.android.accountauthenticator
adb shell pm uninstall -k --user 0 com.nttdocomo.android.cloudset
adb shell pm uninstall -k --user 0 com.nttdocomo.android.sdcardbackup
adb shell pm uninstall -k --user 0 com.nttdocomo.android.initialization
adb shell pm uninstall -k --user 0 com.nttdocomo.android.dhome
adb shell pm uninstall -k --user 0 com.nextbit.app
adb shell pm uninstall -k --user 0 jp.co.nttdocomo.lcsapp
adb shell pm uninstall -k --user 0 jp.co.nttdocomo.carriermail
adb shell pm uninstall -k --user 0 com.android.contacts
adb shell pm uninstall -k --user 0 com.nttdocomo.android.docomoset
adb shell pm uninstall -k --user 0 com.nttdocomo.android.photocollection
adb shell pm uninstall -k --user 0 com.nttdocomo.android.dpoint
adb shell pm uninstall -k --user 0 com.nttdocomo.android.dmenu2
adb shell pm uninstall -k --user 0 com.nttdocomo.keitai.payment
adb shell pm uninstall -k --user 0 com.nttdocomo.android.voicetranslation
adb shell pm uninstall -k --user 0 com.nttdocomo.android.voiceeditor
adb shell pm uninstall -k --user 0 com.nttdocomo.android.mascot
adb shell pm uninstall -k --user 0 com.nttdocomo.android.mydocomo
adb shell pm uninstall -k --user 0 com.nttdocomo.android.networkservice
adb shell pm uninstall -k --user 0 com.nttdocomo.android.store
adb shell pm uninstall -k --user 0 jp.co.nttdocomo.saigaiban
adb shell pm uninstall -k --user 0 jp.co.omronsoft.android.decoemojimanager_docomo
adb shell pm uninstall -k --user 0 com.nttdocomo.android.devicehelp
adb shell pm uninstall -k --user 0 com.nttdocomo.android.schedulememo
adb shell pm uninstall -k --user 0 jp.co.disney.apps.gm.disneydx
adb shell pm uninstall -k --user 0 com.amazon.kindle
adb shell pm uninstall -k --user 0 com.somc.so51a.manual
adb shell pm uninstall -k --user 0 jp.id_credit_sp.android
adb shell pm uninstall -k --user 0 com.nttdocomo.android.phonemotion
adb shell pm uninstall -k --user 0 jp.co.sony.mc.so54c.manual
adb shell pm uninstall -k --user 0 com.nttdocomo.android.applicationmanagerrecommendshortcut
adb shell pm uninstall -k --user 0 com.nttdocomo.android.homezozo
adb shell pm disable-user --user 0 jp.softbank.mb.tdrl
adb install APK/Google_Messages.apk
echo Clearer
echo.
exit

:cmd6
ECHO.===============================================
ECHO.HƯỚNG DẪN BẬT NHÀ PHÁT TRIỂN VÀ BẬT GỠ LỖI USB:
ECHO.===============================================
ECHO.Xiaomi/Redmi: Settings (Cài đặt) -^> My Devices (Thiết bị của tôi) -^> nhấn liên tục 7 lần mục OS version (Phiên bản OS) -^> Thoát ra -^> Vào lại Settings (Cài đặt) -^> Additional settings (Cài đặt bổ sung) -^> Developer options (Tùy chọn cho nhà phát triển) -^> bật USB debugging (Gỡ lỗi qua USB). Sau đó cắm cáp kết nối điện thoại vào máy tính sẽ hiện thông báo bạn bấm cho phép trên điện thoại rồi bấn phím Enter để chạy Tool.
ECHO.===============================================
ECHO.OPPO/Realme/OnePlus: Cài đặt -^> Giới thiệu về thiết bị -^> Phiên bản -^> Số phiên bản (nhấn liên tục 7 lần) -^> Thoát ra -^> Vào lại Cài đặt -^> Hệ thống và cập nhật -^> Tùy chọn nhà phát triển -^> Gỡ lỗi qua USB (bật lên). Sau đó cắm cáp kết nối điện thoại vào máy tính sẽ hiện thông báo bạn bấm cho phép trên điện thoại rồi bấn phím Enter để chạy Tool.
ECHO.===============================================
ECHO.Honor/Huawei: Cài đặt -^> Giới thiệu về điện thoại -^> Số hiệu bảng dựng trên Honor hoặc Phiên bản HarmonyOS trên Huawei (nhấn liên tục 7 lần) -^> Thoát ra -^> Vào lại Cài đặt -^> Hệ thống và cập nhật -^> Tùy chọn nhà phát triển -^> Gỡ lỗi USB (bật lên) -^> Theo dõi ứng dụng do ADB cài (tắt đi). Sau đó cắm cáp kết nối điện thoại vào máy tính sẽ hiện thông báo bạn bấm cho phép trên điện thoại rồi bấn phím Enter để chạy Tool.
ECHO.===============================================
ECHO.Vivo/iQOO: Đối với máy này buộc phải đăng nhập tài khoản Vivo vào trước khi chạy Tool. Vào Cài đặt -^> Giới thiệu về thiết bị -^> Thông tin phiên bản -^> Phiên bản phần mềm (nhấn liên tục 7 lần) [Thoát ra rồi vào lại Cài đặt] -^> Quản lý và nâng cấp hệ thống -^> Tùy chọn nhà phát triển (bật lên) -^> Gỡ lỗi qua USB (bật lên). Sau đó cắm cáp kết nối điện thoại vào máy tính sẽ hiện thông báo bạn bấm cho phép trên điện thoại rồi bấn phím Enter để chạy Tool. 
ECHO.
pause
goto menu

:cmd7
ECHO.[1/3] Đóng các ứng dụng có thể chiếm ADB/USB...
set "KILL_LIST=HiSuite.exe HiSuiteService.exe HiSuiteService64.exe HiSuiteDownloader.exe hdb.exe HonorSuite.exe HonorSuiteService.exe HonorSuiteService64.exe PhoneExperienceHost.exe YourPhone.exe CrossDeviceService.exe scrcpy.exe sndcpy.exe Vysor.exe AirDroid.exe AirDroidCast.exe Mobizen.exe ApowerMirror.exe LetsView.exe MirrorTo.exe 360MobileMgr.exe 360sd.exe 360se.exe wandoujia.exe pea.exe Kies.exe KiesTrayAgent.exe SmartSwitchPC.exe SideSync.exe"
set "KILLED_ANY=0"
for %%P in (%KILL_LIST%) do (
  taskkill /F /T /IM "%%~P" >nul 2>nul
  if not errorlevel 1 (
    echo     -^> Đã tắt %%~P
    set "KILLED_ANY=1"
  )
)
if "%KILLED_ANY%"=="0" (
  echo     -^> Không thấy Xiaomi PC Suite / app truyền màn hình nào đang chạy.
)

rem Tìm adb: canh file này -^> vị trí thường gặp -^> PATH (chỉ để kill-server cho "sạch").
set "ADB="
for %%P in (
  "%~dp0adb.exe"
  "C:\scrcpy\adb.exe"
  "C:\platform-tools\adb.exe"
  "C:\adb\adb.exe"
  "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
) do if not defined ADB if exist "%%~P" set "ADB=%%~P"
if not defined ADB ( where adb >nul 2>nul && set "ADB=adb" )

echo [2/3] Sửa lỗi máy tính không nhận điện thoại...
if defined ADB (
  "%ADB%" kill-server
  echo     -^> Hoàn tất
) else (
  echo     -^> Không tìm thấy adb, bỏ qua ^(bước 2 vẫn nhả cổng USB^).
)

echo [3/3] Tất cả tiến trình adb.exe còn sót lại...
taskkill /F /T /IM adb.exe >nul 2>nul
if errorlevel 1 (
  echo     -^> Không còn tiến trình adb.exe nào đang chạy.
) else (
  echo     -^> Đã tắt các tiến tình adb.exe.
)
goto menu

:exit
exit