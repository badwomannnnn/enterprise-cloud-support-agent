param(
    [Parameter(Mandatory = $true)][string]$TextFile,
    [Parameter(Mandatory = $true)][string]$OutputFile,
    [int]$Rate = -1
)

Add-Type -AssemblyName System.Speech
$text = [System.IO.File]::ReadAllText($TextFile, [System.Text.Encoding]::UTF8)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synth.SelectVoice("Microsoft Huihui Desktop")
    $synth.Rate = $Rate
    $synth.Volume = 100
    $synth.SetOutputToWaveFile($OutputFile)
    $synth.Speak($text)
} finally {
    $synth.Dispose()
}
