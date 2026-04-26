import logging
from typing import List, Optional
from core.models import Product, SourceDescription, GeneratedText
from storage.db import get_connection

logger = logging.getLogger(__name__)


class ProductRepository:
    """CRUD для таблицы products. UPSERT по code."""

    def upsert(self, product: Product) -> None:
        sql = """
            INSERT INTO products (code, name, application, price, source_file)
            VALUES (:code, :name, :application, :price, :source_file)
            ON CONFLICT(code) DO UPDATE SET
                name        = excluded.name,
                application = excluded.application,
                price       = excluded.price,
                source_file = excluded.source_file
        """
        with get_connection() as conn:
            conn.execute(sql, {
                "code": product.code, "name": product.name,
                "application": product.application, "price": product.price,
                "source_file": product.source_file,
            })

    def upsert_batch(self, products: List[Product]) -> int:
        for p in products:
            self.upsert(p)
        logger.info(f"ProductRepository: upserted {len(products)} records")
        return len(products)

    def get_all_codes(self) -> List[str]:
        with get_connection() as conn:
            rows = conn.execute("SELECT code FROM products ORDER BY code").fetchall()
        return [r["code"] for r in rows]

    def get_by_code(self, code: str) -> Optional[Product]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM products WHERE code = ?", (code,)
            ).fetchone()
        if row is None:
            return None
        return Product(
            code=row["code"], name=row["name"],
            application=row["application"], price=row["price"],
            source_file=row["source_file"],
        )


class SourceDescriptionRepository:
    """Сырые описания из источников. UPSERT по (code, source)."""

    def upsert(self, sd: SourceDescription) -> None:
        sql = """
            INSERT INTO source_descriptions (code, source, raw_description)
            VALUES (:code, :source, :raw_description)
            ON CONFLICT(code, source) DO UPDATE SET
                raw_description = excluded.raw_description
        """
        with get_connection() as conn:
            conn.execute(sql, {
                "code": sd.code, "source": sd.source,
                "raw_description": sd.raw_description,
            })

    def upsert_batch(self, items: List[SourceDescription]) -> int:
        for item in items:
            self.upsert(item)
        source_tag = items[0].source if items else "?"
        logger.info(f"SourceDescriptionRepository: upserted {len(items)} records (source={source_tag})")
        return len(items)

    def get_by_code(self, code: str) -> List[SourceDescription]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM source_descriptions WHERE code = ?", (code,)
            ).fetchall()
        return [
            SourceDescription(code=r["code"], source=r["source"], raw_description=r["raw_description"])
            for r in rows
        ]


class GeneratedTextRepository:
    """AI-тексты. UPSERT по (code, text_type)."""

    def upsert(self, gt: GeneratedText) -> None:
        sql = """
            INSERT INTO generated_texts (code, text_type, content, model_id, has_services_block)
            VALUES (:code, :text_type, :content, :model_id, :has_services_block)
            ON CONFLICT(code, text_type) DO UPDATE SET
                content            = excluded.content,
                model_id           = excluded.model_id,
                has_services_block = excluded.has_services_block
        """
        with get_connection() as conn:
            conn.execute(sql, {
                "code": gt.code, "text_type": gt.text_type,
                "content": gt.content, "model_id": gt.model_id,
                "has_services_block": int(gt.has_services_block),
            })

    def upsert_batch(self, items: List[GeneratedText]) -> int:
        for item in items:
            self.upsert(item)
        return len(items)

    def get_codes_without_generated(self, text_type: str = "newdescriptiontop") -> List[str]:
        """Вернуть коды товаров, для которых ещё нет сгенерированного текста данного типа."""
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT p.code FROM products p
                LEFT JOIN generated_texts gt
                    ON p.code = gt.code AND gt.text_type = ?
                WHERE gt.code IS NULL
                ORDER BY p.code
            """, (text_type,)).fetchall()
        return [r["code"] for r in rows]

    def get_by_code(self, code: str, text_type: str = "newdescriptiontop") -> Optional[GeneratedText]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM generated_texts WHERE code = ? AND text_type = ?",
                (code, text_type)
            ).fetchone()
        if row is None:
            return None
        return GeneratedText(
            code=row["code"], text_type=row["text_type"],
            content=row["content"], model_id=row["model_id"],
            has_services_block=bool(row["has_services_block"]),
        )
