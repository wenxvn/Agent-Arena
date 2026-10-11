# 21 新世界 × 5 seeds = 105 局并行（Muse 获胜组合：memory + history5 + recovery + phase + 不限步）。
# 用法：在仓库根目录执行 .\scripts\run_21maps_matrix.ps1
# 每局独立网关 session，trace 进 runs/muse-21maps-<key>-<diff>/，日志进 logs/。

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $root

$configs = @(
    @('polar', 'polar-escape'),
    @('pyramid', 'pyramid-escape'),
    @('subway', 'subway-escape'),
    @('volcano', 'volcano-escape'),
    @('jungle', 'jungle-escape'),
    @('lunar', 'lunar-escape'),
    @('castle', 'castle-escape')
)
$diffs = @('easy', 'med', 'hard')
$versionOf = @{ 'easy' = 'easy-zh'; 'med' = 'v1-zh'; 'hard' = 'hard-zh' }

$procs = @()
foreach ($c in $configs) {
    $key, $slug = $c
    foreach ($d in $diffs) {
        $ver = "$slug-$($versionOf[$d])"
        $tag = "21-$key-$d"
        foreach ($seed in 0..4) {
            $envBlock = @(
                "`$env:PYTHONPATH='src'",
                "`$env:AGENT_ARENA_WORLD='$slug'",
                "`$env:AGENT_ARENA_WORLD_VERSION='$ver'",
                "`$env:AGENT_ARENA_STEP_LIMIT='0'",
                "`$env:AGENT_ARENA_RESPONSE_FORMAT='json_schema'",
                "`$env:OPENAI_SESSION_ID='muse-21maps-$tag-s$seed'"
            ) -join '; '
            $runArgs = "scripts/run_episode.py run --provider openai --agent memory --seed $seed " + `
                "--output-dir runs/muse-21maps-$tag --autonomous " + `
                "--recent-history 5 --stuck-recovery --phase-context"
            $cmd = "$envBlock; python $runArgs"
            $log = "logs/$tag-s$seed.log"
            $p = Start-Process -FilePath 'powershell' -ArgumentList '-NoProfile', '-Command', $cmd `
                -RedirectStandardOutput $log -RedirectStandardError "$log.err" `
                -WorkingDirectory $root -WindowStyle Hidden -PassThru
            $procs += [pscustomobject]@{ Tag = "$tag-s$seed"; Id = $p.Id }
            Write-Output "started $tag-s$seed pid=$($p.Id)"
        }
    }
}
Write-Output "total started: $($procs.Count)"
$procs | Format-Table -AutoSize | Out-String | Write-Output
