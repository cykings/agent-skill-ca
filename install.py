#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ca-skill-bundle 一键安装脚本
# 支持 Claude Code / OpenClaw / OpenAI Codex CLI
# 用法: python install.py

import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 三个工具的 skill 安装路径(用户级)
TARGETS = {
    "1": {
        "name": "Claude Code",
        "skill_dir": Path.home() / ".claude" / "skills" / "ca",
        "invoke": "/ca <CA>",
    },
    "2": {
        "name": "OpenClaw",
        "skill_dir": Path.home() / ".openclaw" / "workspace" / "skills" / "ca",
        "invoke": "/ca <CA>",
    },
    "3": {
        "name": "OpenAI Codex CLI",
        "skill_dir": Path.home() / ".agents" / "skills" / "ca",
        "invoke": "$ca <CA>",
    },
    "4": {
        "name": "全部装一遍",
        "skill_dir": None,
        "invoke": "",
    },
}

REQUIRED_FILES = ["analyze.py", "claim_history.py", "requirements.txt"]


def banner():
    print()
    print("=" * 60)
    print("  /ca skill - 代币合约情报速查 - 跨工具安装器")
    print("=" * 60)
    print()


def pick_target():
    print("请选择要安装到哪个 AI 工具:")
    print()
    for k, v in TARGETS.items():
        path_hint = v["skill_dir"] or "(逐个安装到上面 3 个目录)"
        print(f"  {k}) {v['name']:<20} -> {path_hint}")
    print()
    while True:
        choice = input("输入数字 [1-4]: ").strip()
        if choice in TARGETS:
            return choice
        print("⚠️  无效选择,重试")


def install_to(target):
    name = target["name"]
    skill_dir = target["skill_dir"]
    print(f"\n📦 安装到 {name}: {skill_dir}")

    # 建目录
    skill_dir.mkdir(parents=True, exist_ok=True)

    # 复制脚本和依赖文件
    for fn in REQUIRED_FILES:
        src = HERE / fn
        dst = skill_dir / fn
        if not src.exists():
            print(f"   ⚠️  缺少源文件 {src},跳过")
            continue
        shutil.copy2(src, dst)
        print(f"   ✅ 复制 {fn}")

    # 读 SKILL.template.md, 把 {{SKILL_DIR}} 替换成实际绝对路径
    template = HERE / "SKILL.template.md"
    if not template.exists():
        print(f"   ❌ 缺少 SKILL.template.md,放弃")
        return False
    content = template.read_text(encoding="utf-8")
    # 路径要用 / 而不是 \,跨平台稳一些
    abs_path = str(skill_dir).replace("\\", "/")
    content = content.replace("{{SKILL_DIR}}", abs_path)

    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    print(f"   ✅ 生成 SKILL.md (路径已替换为 {abs_path})")
    return True


def setup_env():
    # 检查 ~/.config/gmgn/.env 是否存在,不存在就提示用 .env.example 创建
    env_path = Path.home() / ".config" / "gmgn" / ".env"
    if env_path.exists():
        print(f"\n✅ API key 配置文件已存在: {env_path}")
        return
    print(f"\n⚠️  API key 配置文件不存在: {env_path}")
    print(f"   建议从 .env.example 复制一份并填入 key:")
    print(f"   1. mkdir -p {env_path.parent}")
    print(f"   2. 复制 {HERE / '.env.example'} 到 {env_path}")
    print(f"   3. 编辑 {env_path},填入至少 GMGN_API_KEY 和 DEEPSEEK_API_KEY")


def post_install_hint(targets_done):
    print()
    print("=" * 60)
    print("  安装完成!后续步骤:")
    print("=" * 60)
    print()
    print("【1】装 Python 依赖")
    print(f"     pip install -r {HERE / 'requirements.txt'}")
    print()
    print("【2】装 gmgn-cli (核心数据源)")
    print(f"     npm install -g gmgn-cli@1.0.1")
    print()
    print("【3】配 API keys (见上方提示)")
    print()
    print("【4】用法:")
    for t in targets_done:
        print(f"     在 {t['name']} 里输入: {t['invoke']}")
    print()
    print("【常见报错】")
    print("  - 'gmgn-cli not found': npm install -g gmgn-cli 没装")
    print("  - 'DEEPSEEK_API_KEY 未配置': ~/.config/gmgn/.env 没填 key")
    print("  - 'analyze.py 失败': 缺 Python 依赖,跑 pip install -r requirements.txt")
    print()


def main():
    banner()
    choice = pick_target()

    if choice == "4":
        targets = [TARGETS["1"], TARGETS["2"], TARGETS["3"]]
    else:
        targets = [TARGETS[choice]]

    done = []
    for t in targets:
        try:
            ok = install_to(t)
            if ok:
                done.append(t)
        except Exception as e:
            print(f"   ❌ 安装 {t['name']} 失败: {e}")

    setup_env()
    post_install_hint(done)


if __name__ == "__main__":
    main()
