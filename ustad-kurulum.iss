; ÜSTAD PC OPTIMIZER — klasik görünümlü kurulum (Inno Setup 6)
; Derleme:  ISCC.exe ustad-kurulum.iss
; Klasik setup akışı: Hoş geldiniz → Klasör seçimi → Kısayollar → Kur → Bitir

#define UygulamaAdi "ÜSTAD PC OPTIMIZER"
#define Surum "1.2.1"
#define Yayinci "ÜSTAD KENAN KUZUCU"
#define KurulumAdi "USTAD-PC-OPTIMIZER-KURULUM-v1.2.1-x64"

[Setup]
AppId={{8B0F4C2A-71D3-4E9B-9C2F-USTADPC0V121}
AppName={#UygulamaAdi}
AppVersion={#Surum}
AppVerName={#UygulamaAdi} {#Surum}
AppPublisher={#Yayinci}
AppComments=Gerçek Windows bakım, izleme ve kurtarma paneli · 64 bit · yerel çalışır, veri göndermez
DefaultDirName={localappdata}\USTAD-PC-OPTIMIZER
DefaultGroupName={#UygulamaAdi}
DisableProgramGroupPage=yes
DisableDirPage=no
DisableWelcomePage=no
DisableReadyPage=no
AllowNoIcons=yes
PrivilegesRequired=lowest
OutputDir=cikti
OutputBaseFilename={#KurulumAdi}
SetupIconFile=kurulum-simgesi.ico
UninstallDisplayIcon={app}\ikon.ico
UninstallDisplayName={#UygulamaAdi} {#Surum}
WizardStyle=classic
WizardImageFile=kurulum-gorselleri\sihirbaz-buyuk.bmp
WizardSmallImageFile=kurulum-gorselleri\sihirbaz-kucuk.bmp
WizardImageStretch=no
Compression=lzma2/max
SolidCompression=yes
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion=1.2.1.0
VersionInfoDescription=ÜSTAD PC OPTIMIZER kurulum programı
VersionInfoCompany=ÜSTAD KENAN KUZUCU
VersionInfoProductName=ÜSTAD PC OPTIMIZER
VersionInfoProductVersion=1.2.1

[Languages]
Name: "turkce"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "masaustu"; Description: "Masaüstüne simge ekle (altın madalyon logosu ile)"; GroupDescription: "Kısayollar:"; Flags: checkedonce
Name: "baslatmenusu"; Description: "Başlat menüsüne ekle"; GroupDescription: "Kısayollar:"; Flags: checkedonce

[Files]
Source: "index.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "sunucu.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "OKU-BENI.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "USTAD-PC-OPTIMIZER.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "YONETICI-OLARAK.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "GITHUB-YEDEKLE.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "ikon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "araclar\*"; DestDir: "{app}\araclar"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "kurulum-gorselleri\setup-ikon-onizleme.png"; DestDir: "{app}\kurulum-gorselleri"; Flags: ignoreversion

[Dirs]
Name: "{app}\kasa"
Name: "{app}\araclar"

[Icons]
Name: "{group}\{#UygulamaAdi}"; Filename: "{app}\USTAD-PC-OPTIMIZER.bat"; WorkingDir: "{app}"; IconFilename: "{app}\ikon.ico"; Comment: "Paneli aç"; Tasks: baslatmenusu
Name: "{group}\{#UygulamaAdi} (Yönetici)"; Filename: "{app}\YONETICI-OLARAK.bat"; WorkingDir: "{app}"; IconFilename: "{app}\ikon.ico"; Comment: "Yönetici haklarıyla aç"; Tasks: baslatmenusu
Name: "{group}\Kullanım Kılavuzu"; Filename: "{app}\OKU-BENI.txt"; Tasks: baslatmenusu
Name: "{group}\Kaldır"; Filename: "{uninstallexe}"; Tasks: baslatmenusu
Name: "{autodesktop}\{#UygulamaAdi}"; Filename: "{app}\USTAD-PC-OPTIMIZER.bat"; WorkingDir: "{app}"; IconFilename: "{app}\ikon.ico"; Comment: "Paneli aç"; Tasks: masaustu
Name: "{autodesktop}\{#UygulamaAdi} (Yönetici)"; Filename: "{app}\YONETICI-OLARAK.bat"; WorkingDir: "{app}"; IconFilename: "{app}\ikon.ico"; Comment: "Yönetici haklarıyla aç"; Tasks: masaustu

[Run]
Filename: "{app}\USTAD-PC-OPTIMIZER.bat"; Description: "ÜSTAD PC OPTIMIZER panelini şimdi aç"; Flags: postinstall shellexec skipifsilent nowait
Filename: "{app}\OKU-BENI.txt"; Description: "Kullanım kılavuzunu aç"; Flags: postinstall shellexec skipifsilent unchecked

[UninstallDelete]
Type: files; Name: "{app}\port.txt"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\tarayici-profil"

[Code]
// Kurulum sonrası kısa bilgi mesajı
function GetCustomSetupExitMessage(): String;
begin
  Result := 'Kurulum tamamlandı.' + #13#10 +
            'Masaüstündeki altın madalyon simgesinden paneli açabilirsin.' + #13#10 +
            'Yönetici işleri için (Yönetici) olan simgeyi kullan.';
end;
