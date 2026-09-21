from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg


ROOT = Path(__file__).resolve().parents[1]
SLIDES = ROOT / "docs" / "rendered" / "slides"
BUILD = ROOT / "docs" / "rendered" / "video-build"
OUTPUT = ROOT / "docs" / "deliverables" / "企业云产品智能支持与工单协同Agent_演示视频.mp4"
POWERSHELL = Path(
    r"C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"
)

NARRATION = [
    "这是一个面向企业云产品咨询和接口故障的智能支持与工单协同 Agent。它不是只会聊天的机器人，而是把知识问答、故障诊断、人工升级和处理记录连接成一条可以解释、测试和审计的流程。",
    "企业客户经常只说接口不能用了，却没有提供错误码、请求标识、发生时间和影响范围。支持人员还要在产品文档、账户信息和工单系统之间切换。本项目的目标，就是先把问题问清楚，再基于证据处理，并保证转交人工时上下文不丢失。",
    "系统前端使用 Streamlit，后端使用 FastAPI 和 Pydantic。Agent 负责决定追问、检索、调用工具还是升级。知识库提供来源依据，Python 工具返回确定性演示数据，工单状态机约束分派、解决和关闭。模型主要负责理解和表达，不允许直接伪造账户或服务状态。",
    "第一条演示主线是知识问答。用户询问 API Key 应该放在哪里，系统从十七篇虚拟产品文档中检索相关片段，再生成带引用的操作说明。检索同时使用文本相似度和错误码精确匹配。如果知识库没有可靠内容，系统会明确拒答，而不是凭常识补全未知事实。",
    "第二条主线是工具诊断。用户报告四二九错误，并提供请求标识、账户和影响范围。系统先完成信息检查，再调用错误码和账户额度工具，返回四二九含义以及演示账户的额度状态。第三条主线是生产环境大面积五零三，系统识别为高风险事件，脱敏联系电话，查询演示服务状态，并创建优先级为 P 一的人工工单。",
    "所有工具都由 Python 真正执行，返回值明确标注为演示环境。工单从新建、补充信息、AI 处理、人工处理、已解决到关闭，每次变化都由后端状态机校验。非法跳转返回四零九。人工解决后，可以记录用户反馈，并把已验证方案标记为候选知识。",
    "为了保证演示稳定和数据安全，系统在模型调用前遮盖密钥、手机号和邮箱，拦截要求绕过规则或索取系统提示的输入。真实模型不可用时自动切换到 Mock 模式；没有知识依据时创建人工工单。日志和时间线保留必要字段，但不会记录原始敏感信息。",
    "项目准备了四十二条固定样例，覆盖可回答问题、同义表达、无答案、追问、工具、人工升级和安全。当前小规模离线集上，分类、召回、工具选择、升级和脱敏检查均为百分之百。这个数字只证明当前流程在固定样例上可重复，不代表生产效果；自然语言答案仍需要人工抽检。",
    "最终交付包括可本地运行的 Demo、完整代码仓库、架构图、两页解决方案、测试报告、九页汇报 PPT 和这段演示视频。下一步会接入真实企业身份权限、服务状态和工单平台，并增加独立盲测集、人工知识审核和线上效果监控。",
]


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / float(handle.getframerate())


def quote_concat(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "'\\''")


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    audio_files: list[Path] = []
    durations: list[float] = []
    for index, text in enumerate(NARRATION, start=1):
        text_path = BUILD / f"segment-{index:02d}.txt"
        wav_path = BUILD / f"segment-{index:02d}.wav"
        text_path.write_text(text, encoding="utf-8")
        run(
            [
                str(POWERSHELL),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "scripts" / "generate_voiceover.ps1"),
                "-TextFile",
                str(text_path),
                "-OutputFile",
                str(wav_path),
                "-Rate",
                "4",
            ]
        )
        audio_files.append(wav_path)
        durations.append(wav_duration(wav_path) + 0.35)

    audio_manifest = BUILD / "audio-concat.txt"
    audio_manifest.write_text(
        "\n".join(f"file '{quote_concat(path)}'" for path in audio_files) + "\n",
        encoding="utf-8",
    )
    narration_wav = BUILD / "narration.wav"
    run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(audio_manifest), "-c:a", "pcm_s16le", str(narration_wav)])

    image_manifest = BUILD / "images-concat.txt"
    image_lines: list[str] = []
    for index, duration in enumerate(durations, start=1):
        image_path = SLIDES / f"slide-{index}.png"
        if not image_path.exists():
            raise FileNotFoundError(f"Missing rendered slide: {image_path}")
        image_lines.extend([f"file '{quote_concat(image_path)}'", f"duration {duration:.3f}"])
    image_lines.append(f"file '{quote_concat(SLIDES / 'slide-9.png')}'")
    image_manifest.write_text("\n".join(image_lines) + "\n", encoding="utf-8")

    silent_video = BUILD / "silent.mp4"
    run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(image_manifest),
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            str(silent_video),
        ]
    )
    run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(narration_wav),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
            str(OUTPUT),
        ]
    )

    metadata = {
        "duration_seconds": round(sum(durations), 2),
        "segments": len(NARRATION),
        "resolution": "1280x720",
        "output": str(OUTPUT),
    }
    (BUILD / "video-metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
