#!/usr/bin/env python3
"""Build/push ECR (linux/amd64). Optional: `start-deployment` when APP_RUNNER_*_ARN is set.

Requires: aws, docker buildx. Frontend build: NEXT_PUBLIC_API_URL, NEXT_PUBLIC_CLERK_*.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, env={**os.environ, **(env or {})})
    if r.returncode != 0:
        sys.exit(r.returncode)


def aws_json(args: list[str]) -> str:
    r = subprocess.run(
        ["aws", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout.strip()


def ecr_registry(region: str) -> str:
    explicit = os.environ.get("ECR_REGISTRY", "").strip()
    if explicit:
        return explicit.rstrip("/")
    account = aws_json(
        [
            "sts",
            "get-caller-identity",
            "--region",
            region,
            "--query",
            "Account",
            "--output",
            "text",
        ]
    )
    return f"{account}.dkr.ecr.{region}.amazonaws.com"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", action="store_true")
    parser.add_argument("--frontend", action="store_true")
    args = parser.parse_args()
    if not args.backend and not args.frontend:
        args.backend = args.frontend = True

    region = os.environ.get("AWS_REGION", "us-east-1")
    tag = os.environ.get("IMAGE_TAG", "amd64").strip() or "amd64"
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    registry = ecr_registry(region)

    pw_proc = subprocess.run(
        ["aws", "ecr", "get-login-password", "--region", region],
        capture_output=True,
        check=True,
    )
    print("+ docker login ...", flush=True)
    subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        input=pw_proc.stdout,
        check=True,
    )

    if args.backend:
        img = f"{registry}/emet-backend:{tag}"
        run(
            [
                "docker",
                "buildx",
                "build",
                "--platform",
                "linux/amd64",
                "--provenance=false",
                "-f",
                os.path.join(repo_root, "backend", "Dockerfile"),
                "-t",
                img,
                "--push",
                os.path.join(repo_root, "backend"),
            ]
        )

    if args.frontend:
        for k in (
            "NEXT_PUBLIC_API_URL",
            "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
            "NEXT_PUBLIC_CLERK_PREMIUM_PLAN_KEY",
        ):
            if not os.environ.get(k, "").strip():
                print(
                    f"Missing env {k} — required for Next.js public env at image build time.",
                    file=sys.stderr,
                )
                sys.exit(1)
        img = f"{registry}/emet-frontend:{tag}"
        run(
            [
                "docker",
                "buildx",
                "build",
                "--platform",
                "linux/amd64",
                "--provenance=false",
                "-f",
                os.path.join(repo_root, "frontend", "Dockerfile"),
                "--build-arg",
                f"NEXT_PUBLIC_API_URL={os.environ['NEXT_PUBLIC_API_URL']}",
                "--build-arg",
                f"NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY={os.environ['NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY']}",
                "--build-arg",
                f"NEXT_PUBLIC_CLERK_PREMIUM_PLAN_KEY={os.environ['NEXT_PUBLIC_CLERK_PREMIUM_PLAN_KEY']}",
                "-t",
                img,
                "--push",
                os.path.join(repo_root, "frontend"),
            ]
        )

    for key, arn_env in (
        ("backend", "APP_RUNNER_BACKEND_ARN"),
        ("frontend", "APP_RUNNER_FRONTEND_ARN"),
    ):
        if not ((args.backend and key == "backend") or (args.frontend and key == "frontend")):
            continue
        arn = os.environ.get(arn_env, "").strip()
        if not arn:
            print(
                f"Skip App Runner start ({key}): set {arn_env} to your service ARN.",
                flush=True,
            )
            continue
        run(
            [
                "aws",
                "apprunner",
                "start-deployment",
                "--service-arn",
                arn,
                "--region",
                region,
            ]
        )


if __name__ == "__main__":
    main()
