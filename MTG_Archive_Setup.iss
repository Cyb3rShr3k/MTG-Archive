; MTG Archive Inno Setup Script
; Creates a professional Windows installer for the MTG Archive application

#define MyAppName "MTG Archive"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "RB LABS"
#define MyAppURL "https://github.com/Cyb3rShr3k/MTG-Archive.git"
#define MyAppExeName "MTG_Archive_Silent.bat"
#define PythonExeName "python.exe"

[Setup]
; Basic application information
AppId={{B7F3E4A1-9C2D-4E5F-8A3B-1D6C7E9F0A2B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE.txt
; Uncomment if you have an info file
; InfoBeforeFile=README.txt
OutputDir=dist
OutputBaseFilename=MTG_Archive_Setup
SetupIconFile=web\assets\icons\MTG Icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main application files
Source: "main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "backend.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "mtg_scanner_gui.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "enrich.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "debug_commander.py"; DestDir: "{app}"; Flags: ignoreversion

; Core modules
Source: "core\*"; DestDir: "{app}\core"; Flags: ignoreversion recursesubdirs createallsubdirs

; Web interface
Source: "web\*"; DestDir: "{app}\web"; Flags: ignoreversion recursesubdirs createallsubdirs

; Assets folder for precon decks
; If Commander.zip exists, it will be extracted during installation
; Otherwise, fall back to individual JSON files
#ifexist "assets\Commander.zip"
Source: "assets\Commander.zip"; DestDir: "{app}\assets"; Flags: ignoreversion
#endif
#ifnexist "assets\Commander.zip"
Source: "assets\Commander\*.json"; DestDir: "{app}\assets\Commander"; Flags: ignoreversion
#endif
Source: "assets\AllDeckFiles\*"; DestDir: "{app}\assets\AllDeckFiles"; Flags: ignoreversion recursesubdirs createallsubdirs

; Database files (if exist)
Source: "cards_db.json"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{#SourcePath}\cards_db.json'))
Source: "app_state.json"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{#SourcePath}\app_state.json'))

; NOTE: MTG_Archive.bat is created during installation by CreateLauncherBatch() procedure

; Documentation (optional - uncomment if README.md exists)
; Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\web\assets\icons\MTG Icon.ico"
Name: "{group}\MTG Card Scanner"; Filename: "{app}\Launch_Scanner.bat"; IconFilename: "{app}\web\assets\icons\Scan Icon.ico"; Comment: "Launch the MTG Card Scanner utility"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\web\assets\icons\MTG Icon.ico"; Tasks: desktopicon
Name: "{autodesktop}\MTG Card Scanner"; Filename: "{app}\Launch_Scanner.bat"; IconFilename: "{app}\web\assets\icons\Scan Icon.ico"; Tasks: desktopicon; Comment: "Launch the MTG Card Scanner utility"

[Run]
Filename: "{cmd}"; Parameters: "/c python --version"; Flags: runhidden waituntilterminated; StatusMsg: "Checking Python installation..."; Check: CheckPython
Filename: "{cmd}"; Parameters: "/c cd /d ""{app}"" && python -m pip install --upgrade pip"; Flags: runhidden waituntilterminated; StatusMsg: "Upgrading pip..."; Check: CheckPython
Filename: "{cmd}"; Parameters: "/c cd /d ""{app}"" && python -m pip install -r requirements.txt"; Flags: runhidden waituntilterminated; StatusMsg: "Installing Python dependencies..."; Check: CheckPython
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent; Check: CheckPython

[Code]
var
  APIKeyPage: TInputQueryWizardPage;
  PythonWarningPage: TOutputMsgWizardPage;
  HasPython: Boolean;
  APIKey: String;
  APIKeyLink: TNewStaticText;

// Forward declarations
procedure OpenAPIKeyURL(Sender: TObject); forward;

// Check if Python is installed
function CheckPython(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  
  // Try to run python --version
  if Exec('cmd.exe', '/c python --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      Result := True;
      HasPython := True;
    end;
  end;
  
  if not Result then
  begin
    HasPython := False;
    MsgBox('Python was not detected on your system.' + #13#10#13#10 +
           'MTG Archive requires Python 3.11 or newer.' + #13#10#13#10 +
           'Please install Python from https://www.python.org/downloads/' + #13#10 +
           'and make sure to check "Add Python to PATH" during installation.' + #13#10#13#10 +
           'After installing Python, run this installer again.', 
           mbError, MB_OK);
  end;
end;

// Initialize wizard pages
procedure InitializeWizard();
begin
  // Check for Python immediately
  CheckPython();
  
  // Create Python warning page if Python is not found
  if not HasPython then
  begin
    PythonWarningPage := CreateOutputMsgPage(wpWelcome,
      'Python Required', 
      'MTG Archive requires Python to run',
      'Python 3.11 or newer was not detected on your system.' + #13#10#13#10 +
      'Please complete the following steps:' + #13#10 +
      '1. Download Python from: https://www.python.org/downloads/' + #13#10 +
      '2. Run the installer' + #13#10 +
      '3. IMPORTANT: Check the box "Add Python to PATH"' + #13#10 +
      '4. Complete the Python installation' + #13#10 +
      '5. Restart this installer' + #13#10#13#10 +
      'Installation will continue but the application will not work without Python.');
  end;

  // Create API Key input page
  APIKeyPage := CreateInputQueryPage(wpSelectDir,
    'OCR.space API Key Required', 
    'MTG Archive needs an OCR.space API key for card scanning',
    'Please obtain a FREE API key from OCR.space and enter it below.' + #13#10#13#10 +
    'Steps to get your API key:' + #13#10 +
    '1. Click the link below to visit OCR.space' + #13#10 +
    '2. Register for a free account (takes 2 minutes)' + #13#10 +
    '3. Copy your API key from the dashboard' + #13#10 +
    '4. Paste it in the field below' + #13#10#13#10);
  
  // Create clickable hyperlink
  APIKeyLink := TNewStaticText.Create(APIKeyPage);
  APIKeyLink.Parent := APIKeyPage.Surface;
  APIKeyLink.Caption := 'Get your FREE API key here: https://ocr.space/ocrapi/freekey';
  APIKeyLink.Font.Color := clBlue;
  APIKeyLink.Font.Style := [fsUnderline];
  APIKeyLink.Cursor := crHand;
  APIKeyLink.OnClick := @OpenAPIKeyURL;
  APIKeyLink.Top := ScaleY(90);
  APIKeyLink.Left := ScaleX(0);
  
  APIKeyPage.Add('API Key:', False);
  APIKeyPage.Values[0] := '';
end;

// Open API key URL in browser
procedure OpenAPIKeyURL(Sender: TObject);
var
  ErrorCode: Integer;
begin
  ShellExec('open', 'https://ocr.space/ocrapi/freekey', '', '', SW_SHOW, ewNoWait, ErrorCode);
end;

// Validate API key before proceeding
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  
  if CurPageID = APIKeyPage.ID then
  begin
    APIKey := Trim(APIKeyPage.Values[0]);
    
    if APIKey = '' then
    begin
      MsgBox('Please enter your OCR.space API key.' + #13#10#13#10 +
             'The API key is FREE and required for card scanning functionality.' + #13#10#13#10 +
             'Visit https://ocr.space/ocrapi/freekey to get your key.', 
             mbError, MB_OK);
      Result := False;
    end
    else
    begin
      // API key provided, we'll configure it after installation
      Result := True;
    end;
  end;
end;

// Create the launcher batch file
procedure CreateLauncherBatch();
var
  BatchContent: String;
  BatchFile: String;
  ScannerBatchContent: String;
  ScannerBatchFile: String;
begin
  BatchFile := ExpandConstant('{app}\MTG_Archive_Silent.bat');
  ScannerBatchFile := ExpandConstant('{app}\Launch_Scanner.bat');
  
  // Create batch file that runs Python without showing console window
  // Using START with /B (background) and pythonw (windowless Python)
  BatchContent := '@echo off' + #13#10 +
                  'cd /d "%~dp0"' + #13#10 +
                  'if not ERRORLEVEL 1 start /B pythonw.exe main.py' + #13#10;
  
  SaveStringToFile(BatchFile, BatchContent, False);
  
  // Create batch file to launch scanner that STAYS OPEN to show errors
  ScannerBatchContent := '@echo off' + #13#10 +
                         'cd /d "%~dp0"' + #13#10 +
                         'echo Starting MTG Scanner GUI...' + #13#10 +
                         'echo.' + #13#10 +
                         'python.exe mtg_scanner_gui.py' + #13#10 +
                         'echo.' + #13#10 +
                         'if errorlevel 1 (' + #13#10 +
                         '    echo.' + #13#10 +
                         '    echo ERROR: Scanner failed to start!' + #13#10 +
                         '    echo Check the error message above.' + #13#10 +
                         ')' + #13#10 +
                         'echo.' + #13#10 +
                         'pause' + #13#10;
  
  SaveStringToFile(ScannerBatchFile, ScannerBatchContent, False);
end;

// Configure API key in mtg_scanner_gui.py after installation
procedure ConfigureAPIKey();
var
  FileName: String;
  FileLines: TArrayOfString;
  I: Integer;
  Modified: Boolean;
begin
  if APIKey <> '' then
  begin
    FileName := ExpandConstant('{app}\mtg_scanner_gui.py');
    
    if LoadStringsFromFile(FileName, FileLines) then
    begin
      Modified := False;
      for I := 0 to GetArrayLength(FileLines) - 1 do
      begin
        if Pos('OCR_SPACE_API_KEY', FileLines[I]) > 0 then
        begin
          FileLines[I] := 'OCR_SPACE_API_KEY = "' + APIKey + '"';
          Modified := True;
          Break;
        end;
      end;
      
      if Modified then
        SaveStringsToFile(FileName, FileLines, False);
    end;
  end;
end;

// Extract Commander.zip if it exists using native Windows PowerShell
procedure ExtractCommanderZip();
var
  ZipFile: String;
  DestDir: String;
  ResultCode: Integer;
begin
  ZipFile := ExpandConstant('{app}\assets\Commander.zip');
  DestDir := ExpandConstant('{app}\assets\Commander');
  
  if FileExists(ZipFile) then
  begin
    // Create destination directory if it doesn't exist
    if not DirExists(DestDir) then
      CreateDir(DestDir);
    
    // Use PowerShell Expand-Archive (built into Windows, no external tools needed)
    Exec('powershell.exe', 
         '-NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path ''' + ZipFile + ''' -DestinationPath ''' + DestDir + ''' -Force"',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    
    // Delete the zip file after successful extraction
    if ResultCode = 0 then
      DeleteFile(ZipFile);
  end;
end;

// Run configuration after installation completes
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    CreateLauncherBatch();
    ConfigureAPIKey();
    ExtractCommanderZip();
  end;
end;

// Show installation summary
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
  begin
    if not HasPython then
    begin
      MsgBox('Installation complete, but Python was not detected.' + #13#10#13#10 +
             'To use MTG Archive:' + #13#10 +
             '1. Install Python 3.11+ from https://www.python.org/downloads/' + #13#10 +
             '2. Make sure to check "Add Python to PATH"' + #13#10 +
             '3. Then run MTG Archive from the Start Menu or Desktop shortcut', 
             mbInformation, MB_OK);
    end;
  end;
end;
