from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parent
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class ImageRecord:
    influencer: str
    image_path: str
    tipo_post: str
    visualizacoes: int | None
    visualizacoes_fonte: str | None
    interacoes: int | None
    interacoes_fonte: str | None
    dedupe_key: str | None
    status: str
    sha1: str
    raw_text: str


def iter_images(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def normalize_text(text: str) -> str:
    text = text.replace("\u2014", "-").replace("\u2013", "-")
    text = text.replace("©", " ").replace("|", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def ocr_image(image_path: Path) -> str:
    attempts = [("original", image_path), ("processed", preprocess_image(image_path))]
    texts: list[str] = []
    for _, attempt_path in attempts:
        for psm in ("6", "11"):
            cmd = [
                "tesseract",
                str(attempt_path),
                "stdout",
                "-l",
                "por+eng",
                "--psm",
                psm,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            text = normalize_text(proc.stdout)
            if text:
                texts.append(text)
        if attempt_path != image_path and attempt_path.exists():
            attempt_path.unlink(missing_ok=True)

    if not texts:
        return ""

    merged_lines: list[str] = []
    seen_lines: set[str] = set()
    for text in texts:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            key = line.lower()
            if key not in seen_lines:
                seen_lines.add(key)
                merged_lines.append(line)
    return "\n".join(merged_lines)


def preprocess_image(image_path: Path) -> Path:
    img = Image.open(image_path).convert("L")
    img = ImageOps.autocontrast(img)
    img = img.point(lambda p: 255 if p > 150 else 0)
    fd, tmp_name = tempfile.mkstemp(suffix=".png")
    Path(tmp_name).unlink(missing_ok=True)
    out = Path(tmp_name)
    img.save(out)
    return out


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_number(token: str) -> int | None:
    token = token.strip().lower()
    token = token.replace("o", "0") if re.fullmatch(r"[o0]+", token) else token
    token = token.replace("%", "")
    token = token.replace(" ", "")
    token = token.replace("mil", "k")
    token = token.replace("mi", "m")
    if not token:
        return None

    multiplier = 1
    if token.endswith("k"):
        multiplier = 1_000
        token = token[:-1]
    elif token.endswith("m"):
        multiplier = 1_000_000
        token = token[:-1]

    if not re.search(r"\d", token):
        return None

    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif token.count(",") == 1:
        left, right = token.split(",")
        if len(right) <= 2:
            token = f"{left}.{right}"
        else:
            token = left + right
    elif token.count(".") >= 1:
        parts = token.split(".")
        if len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
            token = "".join(parts)

    try:
        value = float(token)
    except ValueError:
        digits = re.sub(r"[^\d]", "", token)
        if not digits:
            return None
        value = float(digits)

    return int(round(value * multiplier))


def number_from_line(line: str) -> int | None:
    matches = re.findall(r"\d[\d.,]*\s*[kKmM]?", line)
    for token in reversed(matches):
        value = parse_number(token)
        if value is not None:
            return value
    return None


def detect_type(path: Path, text: str) -> str:
    upper_parts = " / ".join(part.upper() for part in path.parts)
    lower_text = text.lower()
    feed_markers = (
        "insights do reel",
        "insights do post",
        "comentários",
        "comentarios",
        "salvamentos",
        "reposts",
        "curtidas",
        "publicação",
        "publicacao",
    )
    story_markers = (
        "próximo story",
        "proximo story",
        "navegação",
        "navegacao",
        "avanço",
        "avanco",
        "saiu",
        "respostas",
    )
    if "STORIES" in upper_parts:
        return "stories"
    if "REELS" in upper_parts:
        return "feed"
    if any(marker in lower_text for marker in story_markers):
        return "stories"
    if any(marker in lower_text for marker in feed_markers):
        return "feed"
    if "visão geral" in lower_text or "visualizações" in lower_text or "visualizacoes" in lower_text:
        return "stories"
    return "desconhecido"


def extract_visualizations(text: str) -> tuple[int | None, str | None]:
    priorities = [
        ("visualizações", "visualizacoes"),
        ("contas alcançadas", "contas_alcancadas"),
        ("alcance", "alcance"),
    ]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for label, source in priorities:
        for line in lines:
            line_lower = line.lower()
            if label in line_lower:
                value = number_from_line(line)
                if value is not None:
                    return value, source
    return None, None


def extract_interactions(text: str) -> tuple[int | None, str | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        if "interações" in line.lower() or "interacoes" in line.lower():
            value = number_from_line(line)
            if value is not None:
                return value, "interacoes"

    labels = (
        "curtidas",
        "comentários",
        "comentarios",
        "compartilhamentos",
        "salvamentos",
        "reposts",
        "respostas",
    )
    total = 0
    found = False
    for line in lines:
        lowered = line.lower()
        if any(label in lowered for label in labels):
            value = number_from_line(line)
            if value is not None:
                total += value
                found = True
    if found:
        return total, "soma_componentes"
    return None, None


def should_keep(record: ImageRecord) -> bool:
    return record.visualizacoes is not None and record.interacoes is not None


def build_record(path: Path, sha1: str) -> ImageRecord:
    influencer = path.relative_to(ROOT).parts[0]
    text = ocr_image(path)
    tipo_post = detect_type(path.relative_to(ROOT), text)
    visualizacoes, views_source = extract_visualizations(text)
    interacoes, interactions_source = extract_interactions(text)

    dedupe_key = None
    status = "ignored_missing_metrics"
    if should_keep(
        ImageRecord(
            influencer=influencer,
            image_path=str(path.relative_to(ROOT)),
            tipo_post=tipo_post,
            visualizacoes=visualizacoes,
            visualizacoes_fonte=views_source,
            interacoes=interacoes,
            interacoes_fonte=interactions_source,
            dedupe_key=None,
            status="",
            sha1=sha1,
            raw_text=text,
        )
    ):
        dedupe_key = f"{influencer}|{tipo_post}|{visualizacoes}|{interacoes}"
        status = "candidate"

    return ImageRecord(
        influencer=influencer,
        image_path=str(path.relative_to(ROOT)),
        tipo_post=tipo_post,
        visualizacoes=visualizacoes,
        visualizacoes_fonte=views_source,
        interacoes=interacoes,
        interacoes_fonte=interactions_source,
        dedupe_key=dedupe_key,
        status=status,
        sha1=sha1,
        raw_text=text,
    )


def process_images() -> list[ImageRecord]:
    seen_sha1: dict[str, ImageRecord] = {}
    records: list[ImageRecord] = []

    for image_path in sorted(iter_images(ROOT)):
        sha1 = sha1_file(image_path)
        if sha1 in seen_sha1:
            base = seen_sha1[sha1]
            duplicate = ImageRecord(
                influencer=base.influencer,
                image_path=str(image_path.relative_to(ROOT)),
                tipo_post=base.tipo_post,
                visualizacoes=base.visualizacoes,
                visualizacoes_fonte=base.visualizacoes_fonte,
                interacoes=base.interacoes,
                interacoes_fonte=base.interacoes_fonte,
                dedupe_key=base.dedupe_key,
                status="ignored_exact_duplicate_file",
                sha1=sha1,
                raw_text=base.raw_text,
            )
            records.append(duplicate)
            continue

        record = build_record(image_path, sha1)
        seen_sha1[sha1] = record
        records.append(record)

    return records


def aggregate(records: list[ImageRecord]) -> tuple[list[dict[str, object]], list[ImageRecord]]:
    winners_by_key: dict[str, ImageRecord] = {}
    for record in records:
        if record.status != "candidate" or not record.dedupe_key:
            continue
        if record.dedupe_key not in winners_by_key:
            winners_by_key[record.dedupe_key] = record
        else:
            record.status = "ignored_metric_duplicate"

    kept_records = sorted(winners_by_key.values(), key=lambda r: (r.influencer, r.image_path))
    influencers = sorted(
        {
            path.name.strip()
            for path in ROOT.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        }
    )

    rows: list[dict[str, object]] = []
    for influencer in influencers:
        subset = [r for r in kept_records if r.influencer == influencer]
        total_views = sum(r.visualizacoes or 0 for r in subset)
        total_interactions = sum(r.interacoes or 0 for r in subset)
        rate = (total_interactions / total_views) if total_views else 0
        rows.append(
            {
                "influencer": influencer,
                "visualizacoes_totais": total_views,
                "interacoes_totais": total_interactions,
                "taxa_interacao": f"{rate:.6f}",
                "qtd_posts_feed": sum(1 for r in subset if r.tipo_post == "feed"),
                "qtd_posts_stories": sum(1 for r in subset if r.tipo_post == "stories"),
            }
        )
    return rows, kept_records


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "influencer",
                "visualizacoes_totais",
                "interacoes_totais",
                "taxa_interacao",
                "qtd_posts_feed",
                "qtd_posts_stories",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_detail(records: list[ImageRecord], kept_records: list[ImageRecord]) -> None:
    detail_path = ROOT / "instagram_influencers_metrics_detail.csv"
    with detail_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "influencer",
                "image_path",
                "tipo_post",
                "visualizacoes",
                "visualizacoes_fonte",
                "interacoes",
                "interacoes_fonte",
                "dedupe_key",
                "status",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "influencer": record.influencer,
                    "image_path": record.image_path,
                    "tipo_post": record.tipo_post,
                    "visualizacoes": record.visualizacoes,
                    "visualizacoes_fonte": record.visualizacoes_fonte,
                    "interacoes": record.interacoes,
                    "interacoes_fonte": record.interacoes_fonte,
                    "dedupe_key": record.dedupe_key,
                    "status": record.status,
                }
            )

    audit = {
        "kept_records_count": len(kept_records),
        "sample_kept_records": [asdict(record) for record in kept_records[:10]],
        "ignored_by_status": {
            status: sum(1 for record in records if record.status == status)
            for status in sorted({record.status for record in records})
        },
    }
    (ROOT / "instagram_influencers_metrics_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    records = process_images()
    summary_rows, kept_records = aggregate(records)
    write_csv(summary_rows, ROOT / "instagram_influencers_metrics.csv")
    write_detail(records, kept_records)


if __name__ == "__main__":
    main()
