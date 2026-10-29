-- Base source MySQL (RH) : schema de reference, repliquee vers PostgreSQL via Airbyte
CREATE DATABASE IF NOT EXISTS rh_source CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE rh_source;

CREATE TABLE services (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    code          VARCHAR(10)  NOT NULL UNIQUE,
    nom           VARCHAR(100) NOT NULL,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE fonctions (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    code          VARCHAR(10)  NOT NULL UNIQUE,
    libelle       VARCHAR(100) NOT NULL,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE employes (
    matricule     VARCHAR(12)  PRIMARY KEY,
    nom           VARCHAR(80)  NOT NULL,
    prenom        VARCHAR(80)  NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    service_id    INT          NOT NULL,
    fonction_id   INT          NOT NULL,
    date_embauche DATE         NOT NULL,
    actif         TINYINT(1)   NOT NULL DEFAULT 1,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_emp_service  FOREIGN KEY (service_id)  REFERENCES services(id),
    CONSTRAINT fk_emp_fonction FOREIGN KEY (fonction_id) REFERENCES fonctions(id),
    INDEX idx_emp_service  (service_id),
    INDEX idx_emp_fonction (fonction_id),
    INDEX idx_emp_updated  (updated_at)
) ENGINE=InnoDB;

-- Compte dedie, lecture seule, utilise par Airbyte pour l'extraction (principe du moindre privilege)
CREATE USER IF NOT EXISTS 'airbyte_reader'@'%' IDENTIFIED BY 'airbyte_reader_pwd';
GRANT SELECT ON rh_source.* TO 'airbyte_reader'@'%';
FLUSH PRIVILEGES;
