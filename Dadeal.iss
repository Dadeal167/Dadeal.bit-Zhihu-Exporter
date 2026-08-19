; Inno Setup 编译脚本
; 所有源路径均基于脚本所在目录解析，项目搬家后无需再改路径
; 版本号与 core/version.py 保持一致
#define MyAppSourcePath SourcePath
#define MyAppVersion "1.1.1"

[Setup]
AppName=Dadealbit——知乎文章回答内容提取器
AppVersion={#MyAppVersion}
AppPublisher=Dadealbit
DefaultDirName={autopf}\DadealZhihuExporter
DefaultGroupName=Dadealbit——知乎文章回答内容提取器
OutputBaseFilename=Dadealbit_ZhihuExporter_v{#MyAppVersion}_Setup
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile={#MyAppSourcePath}\icon.ico
OutputDir={#MyAppSourcePath}\Output

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkablealone

[Files]
Source: "{#MyAppSourcePath}\dist\main\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#MyAppSourcePath}\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyAppSourcePath}\VC_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\Dadealbit——知乎文章回答内容提取器"; Filename: "{app}\DadealbitZhihuExporter.exe"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\Dadealbit——知乎文章回答内容提取器"; Filename: "{app}\DadealbitZhihuExporter.exe"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"

[Run]
Filename: "{tmp}\VC_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "正在配置底层运行环境，请稍候..."; Flags: waituntilterminated
Filename: "{app}\DadealbitZhihuExporter.exe"; Description: "{cm:LaunchProgram,Dadealbit——知乎文章回答内容提取器}"; Flags: nowait postinstall skipifsilent
