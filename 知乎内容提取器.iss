; Inno Setup 编译脚本
; 所有源路径均基于脚本所在目录解析，项目搬家后无需再改路径
#define MyAppSourcePath SourcePath

[Setup]
AppName=Dadeal.bit——知乎内容提取器
AppVersion=1.0.2
AppPublisher=Dadeal.bit
DefaultDirName={autopf}\DadealZhihuExporter
DefaultGroupName=Dadeal.bit——知乎内容提取器
OutputBaseFilename=Dadeal_ZhihuExporter_v1.0.2_Setup
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
Name: "{group}\Dadeal.bit——知乎内容提取器"; Filename: "{app}\main.exe"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\Dadeal.bit——知乎内容提取器"; Filename: "{app}\main.exe"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"

[Run]
Filename: "{tmp}\VC_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "正在配置底层运行环境，请稍候..."; Flags: waituntilterminated
Filename: "{app}\main.exe"; Description: "{cm:LaunchProgram,Dadeal.bit——知乎内容提取器}"; Flags: nowait postinstall skipifsilent
