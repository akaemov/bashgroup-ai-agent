"""Register real project materials, without claiming an AI has analysed them."""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db_config import database_url
from sqlalchemy import create_engine, text


def main():
    root = Path(__file__).resolve().parents[2]
    skill = (root / "competitor_agent/skills/SKILL.md").read_text()
    digest = hashlib.sha256(skill.encode()).hexdigest()
    agents = [
        ("competitive_intelligence", "Конкурентная разведка"),
        ("proposals", "Коммерческие предложения"),
        ("market", "Анализ рынка"),
        ("prospects", "Поиск заказчиков"),
        ("procurement", "Анализ закупок"),
    ]
    with create_engine(database_url("migrator")).begin() as conn:
        conn.execute(text("SET ROLE bashgroup_owner"))
        for code, name in agents:
            conn.execute(text("INSERT INTO app.agents(code,name) VALUES (:code,:name) ON CONFLICT (code) DO NOTHING"), {"code": code, "name": name})
        agent_id = conn.execute(text("SELECT id FROM app.agents WHERE code='competitive_intelligence'")).scalar_one()
        conn.execute(text("""INSERT INTO app.skill_versions(agent_id,version,sha256,instructions)
            VALUES (:agent_id,:version,:sha,:content) ON CONFLICT (agent_id,sha256) DO NOTHING"""),
            {"agent_id": agent_id, "version": "sha256:" + digest, "sha": digest, "content": skill})
        for candidate in ("АЛБЕС", "Анкер", "Химмель", "Элвер", "Зилант"):
            conn.execute(text("INSERT INTO app.companies(candidate_name) VALUES (:name) ON CONFLICT (candidate_name) DO NOTHING"), {"name": candidate})
        files = [root / "katalog-produktsii.md", *sorted((root / "cases").glob("*.md"))]
        for path in files:
            content = path.read_text()
            conn.execute(text("""INSERT INTO app.materials(kind,title,locator,sha256,content,access_scope)
                VALUES (:kind,:title,:locator,:sha,:content,'public') ON CONFLICT (locator,sha256) DO NOTHING"""), {
                    "kind": "catalog" if path.name == "katalog-produktsii.md" else "case",
                    "title": next((line.lstrip("# ") for line in content.splitlines() if line.startswith("# ")), path.stem),
                    "locator": str(path.relative_to(root)), "sha": hashlib.sha256(path.read_bytes()).hexdigest(), "content": content,
                })
        # Migration metadata must not be writable by the runtime account.
        conn.execute(text("REVOKE ALL ON app.alembic_version FROM bashgroup_app"))
        conn.execute(text("GRANT SELECT ON app.alembic_version TO bashgroup_app"))
    print(f"Registered 5 agents, 5 candidates, skill and {len(files)} materials (not AI-analysed).")


if __name__ == "__main__":
    main()
