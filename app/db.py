"""Conexão com MySQL/MariaDB e criação do esquema, sem apagar dados existentes."""

import os
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from app.qualidade import CAPACIDADE_CAIXA


def _config(com_banco: bool) -> dict:
    cfg = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
    }
    if com_banco:
        cfg["database"] = os.getenv("DB_NAME", "gestao_pecas")
    return cfg


def init_db() -> None:
    nome = os.getenv("DB_NAME", "gestao_pecas")
    conn = pymysql.connect(**_config(False))
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{nome}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()

    conn = pymysql.connect(**_config(True))
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS caixas (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  numero INT NOT NULL UNIQUE,
                  status ENUM('aberta', 'fechada') NOT NULL DEFAULT 'aberta',
                  capacidade INT NOT NULL DEFAULT %s,
                  criada_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  fechada_em DATETIME NULL
                ) ENGINE=InnoDB
                """,
                (CAPACIDADE_CAIXA,),
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS usuarios (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  nome VARCHAR(80) NOT NULL,
                  email VARCHAR(120) NOT NULL UNIQUE,
                  senha_hash VARCHAR(255) NOT NULL,
                  ativo TINYINT(1) NOT NULL DEFAULT 1,
                  refresh_token VARCHAR(700) NULL,
                  ultimo_login DATETIME NULL,
                  falhas_login INT NOT NULL DEFAULT 0,
                  bloqueado_ate DATETIME NULL,
                  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS eventos_seguranca (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  tipo VARCHAR(40) NOT NULL,
                  email VARCHAR(120) NULL,
                  ip VARCHAR(64) NULL,
                  detalhe VARCHAR(255) NULL,
                  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pecas (
                  id VARCHAR(40) PRIMARY KEY,
                  peso DECIMAL(8,2) NOT NULL,
                  cor VARCHAR(30) NOT NULL,
                  comprimento DECIMAL(8,2) NOT NULL,
                  status ENUM('aprovada', 'reprovada') NOT NULL,
                  motivos JSON NULL,
                  caixa_id INT NULL,
                  criada_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  CONSTRAINT fk_peca_caixa FOREIGN KEY (caixa_id) REFERENCES caixas (id)
                ) ENGINE=InnoDB
                """
            )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def conexao():
    conn = pymysql.connect(**_config(True))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
