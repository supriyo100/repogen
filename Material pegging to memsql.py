#!/usr/bin/env python3
"""
Material Pegging BOM Creation & MemSQL Integration
Converts Biocon material files to MemSQL tables with pegging logic

Key Features:
- Reads from Excel (DP Shortage, ParkourSC_SNP)
- Creates normalized tables in MemSQL
- Handles hierarchy (Packing → Assembly → Filling)
- Supports resource mapping
- Maintains data quality checks
"""

import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error
import re
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('material_pegging_memsql.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# MEMSQL CONNECTION CONFIGURATION
# ============================================================================

MEMSQL_CONFIG = {
    'host': 'your-memsql-host.com',      # ← Update with your MemSQL host
    'user': 'root',                       # ← Update with your username
    'password': 'your-password',          # ← Update with your password
    'database': 'biocon_optimization',    # Database name
    'port': 3306,
    'autocommit': False
}

# ============================================================================
# NORMALIZATION FUNCTIONS
# ============================================================================

def normalize_text(text: any) -> Optional[str]:
    """Normalize text: strip, collapse spaces"""
    if pd.isna(text) or text is None:
        return None
    text = str(text).strip()
    text = re.sub(r'\s+', ' ', text)
    return text if text else None

def normalize_product_no(value: any) -> Optional[str]:
    """Extract alphanumeric only from product number"""
    if pd.isna(value) or value is None:
        return None
    text = str(value).strip()
    cleaned = re.sub(r'[^a-zA-Z0-9]', '', text)
    return cleaned if cleaned else None

def extract_model_components(model_text: any) -> Optional[str]:
    """Extract and normalize model components"""
    if pd.isna(model_text):
        return None
    model_text = str(model_text).strip()
    components = re.split(r'_+', model_text)
    components = [c.strip() for c in components if c.strip()]
    return '_'.join(components)

def is_valid_qty(qty: any) -> bool:
    """Check if quantity is valid (> 0, not blank, not NaN)"""
    if pd.isna(qty):
        return False
    qty_str = str(qty).strip()
    if not qty_str or qty_str == '0' or qty_str == 'nan':
        return False
    try:
        return float(qty_str) > 0
    except (ValueError, TypeError):
        return False

# ============================================================================
# MEMSQL CONNECTION MANAGEMENT
# ============================================================================

class MemSQLConnector:
    """Manage MemSQL connections and operations"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.connection = None
        self.cursor = None
    
    def connect(self) -> bool:
        """Establish connection to MemSQL"""
        try:
            self.connection = mysql.connector.connect(**self.config)
            self.cursor = self.connection.cursor()
            logger.info(f"Connected to MemSQL: {self.config['host']}:{self.config['port']}")
            return True
        except Error as e:
            logger.error(f"MemSQL Connection Error: {e}")
            return False
    
    def close(self):
        """Close connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            logger.info("MemSQL connection closed")
    
    def execute_query(self, query: str, params: Tuple = None) -> bool:
        """Execute single query"""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return True
        except Error as e:
            logger.error(f"Query Error: {e}\nQuery: {query}")
            return False
    
    def executemany_query(self, query: str, data: List[Tuple]) -> int:
        """Execute batch insert"""
        try:
            self.cursor.executemany(query, data)
            logger.info(f"Inserted {self.cursor.rowcount} rows")
            return self.cursor.rowcount
        except Error as e:
            logger.error(f"Batch Insert Error: {e}")
            return 0
    
    def commit(self):
        """Commit transaction"""
        try:
            self.connection.commit()
            logger.info("Transaction committed")
        except Error as e:
            logger.error(f"Commit Error: {e}")
    
    def rollback(self):
        """Rollback transaction"""
        try:
            self.connection.rollback()
            logger.warning("Transaction rolled back")
        except Error as e:
            logger.error(f"Rollback Error: {e}")

# ============================================================================
# TABLE CREATION SCHEMAS
# ============================================================================

def create_tables(connector: MemSQLConnector) -> bool:
    """Create all required MemSQL tables"""
    
    tables = {
        'materials': """
            CREATE TABLE IF NOT EXISTS materials (
                material_id VARCHAR(50) PRIMARY KEY,
                material_code VARCHAR(100) UNIQUE NOT NULL,
                material_description VARCHAR(500),
                section VARCHAR(100),
                common_unique VARCHAR(50),
                total_lead_time_weeks FLOAT,
                buom VARCHAR(50),
                model VARCHAR(200),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_material_code (material_code),
                INDEX idx_section (section)
            ) ENGINE=InnoDB;
        """,
        
        'products': """
            CREATE TABLE IF NOT EXISTS products (
                product_id VARCHAR(50) PRIMARY KEY,
                product_code VARCHAR(100) UNIQUE NOT NULL,
                product_description VARCHAR(500),
                product_family VARCHAR(100),
                hierarchy_level VARCHAR(50),
                bom_type VARCHAR(50),
                batch_size VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_product_code (product_code),
                INDEX idx_product_family (product_family),
                INDEX idx_hierarchy_level (hierarchy_level)
            ) ENGINE=InnoDB;
        """,
        
        'skus': """
            CREATE TABLE IF NOT EXISTS skus (
                sku_id VARCHAR(50) PRIMARY KEY,
                sku_code VARCHAR(100) UNIQUE NOT NULL,
                sku_description VARCHAR(500),
                product_family VARCHAR(100),
                pack_size VARCHAR(50),
                country VARCHAR(100),
                region VARCHAR(50),
                assembly_product_id VARCHAR(50),
                filling_product_id VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_sku_code (sku_code),
                INDEX idx_product_family (product_family),
                INDEX idx_region (region),
                FOREIGN KEY (assembly_product_id) REFERENCES products(product_id),
                FOREIGN KEY (filling_product_id) REFERENCES products(product_id)
            ) ENGINE=InnoDB;
        """,
        
        'bom_hierarchy': """
            CREATE TABLE IF NOT EXISTS bom_hierarchy (
                hierarchy_id INT AUTO_INCREMENT PRIMARY KEY,
                sku_id VARCHAR(50) NOT NULL,
                level INT NOT NULL,
                product_id VARCHAR(50) NOT NULL,
                product_description VARCHAR(500),
                material_id VARCHAR(50) NOT NULL,
                material_description VARCHAR(500),
                quantity FLOAT NOT NULL,
                section VARCHAR(100),
                common_unique VARCHAR(50),
                buom VARCHAR(50),
                lead_time_weeks FLOAT,
                resource_id VARCHAR(100),
                resource_description VARCHAR(300),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_sku_id (sku_id),
                INDEX idx_level (level),
                INDEX idx_product_id (product_id),
                INDEX idx_material_id (material_id),
                FOREIGN KEY (sku_id) REFERENCES skus(sku_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id),
                FOREIGN KEY (material_id) REFERENCES materials(material_id)
            ) ENGINE=InnoDB;
        """,
        
        'resources': """
            CREATE TABLE IF NOT EXISTS resources (
                resource_id VARCHAR(100) PRIMARY KEY,
                resource_description VARCHAR(500),
                molecule VARCHAR(100),
                product_id VARCHAR(50),
                stage VARCHAR(50),
                capacity_per_day FLOAT,
                changeover_hours FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_product_id (product_id),
                INDEX idx_stage (stage),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            ) ENGINE=InnoDB;
        """,
        
        'routing_rules': """
            CREATE TABLE IF NOT EXISTS routing_rules (
                rule_id VARCHAR(50) PRIMARY KEY,
                rule_description VARCHAR(500),
                resource_id VARCHAR(100),
                rule_type VARCHAR(50),
                stage VARCHAR(50),
                priority INT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_resource_id (resource_id),
                INDEX idx_stage (stage),
                INDEX idx_is_active (is_active)
            ) ENGINE=InnoDB;
        """,
        
        'sku_demand': """
            CREATE TABLE IF NOT EXISTS sku_demand (
                demand_id INT AUTO_INCREMENT PRIMARY KEY,
                sku_id VARCHAR(50) NOT NULL,
                molecule VARCHAR(100),
                product_form VARCHAR(50),
                region VARCHAR(50),
                q3_fy26 FLOAT,
                q4_fy26 FLOAT,
                q1_fy27 FLOAT,
                q2_fy27 FLOAT,
                total_demand FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_sku_id (sku_id),
                INDEX idx_molecule (molecule),
                INDEX idx_region (region),
                FOREIGN KEY (sku_id) REFERENCES skus(sku_id)
            ) ENGINE=InnoDB;
        """,
        
        'data_quality_log': """
            CREATE TABLE IF NOT EXISTS data_quality_log (
                log_id INT AUTO_INCREMENT PRIMARY KEY,
                check_type VARCHAR(100),
                entity_type VARCHAR(50),
                entity_id VARCHAR(100),
                issue_description VARCHAR(500),
                severity VARCHAR(20),
                status VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                INDEX idx_entity_type (entity_type),
                INDEX idx_severity (severity),
                INDEX idx_status (status)
            ) ENGINE=InnoDB;
        """,
        
        'pegging_audit_trail': """
            CREATE TABLE IF NOT EXISTS pegging_audit_trail (
                audit_id INT AUTO_INCREMENT PRIMARY KEY,
                sku_id VARCHAR(50) NOT NULL,
                product_id VARCHAR(50),
                material_id VARCHAR(50),
                action VARCHAR(50),
                old_value VARCHAR(500),
                new_value VARCHAR(500),
                changed_by VARCHAR(100),
                change_reason VARCHAR(300),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_sku_id (sku_id),
                INDEX idx_action (action),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB;
        """
    }
    
    logger.info("Creating MemSQL tables...")
    for table_name, create_sql in tables.items():
        if connector.execute_query(create_sql):
            logger.info(f"✓ Table '{table_name}' created/verified")
        else:
            logger.error(f"✗ Failed to create table '{table_name}'")
            return False
    
    connector.commit()
    logger.info("All tables created successfully")
    return True

# ============================================================================
# DATA LOADING FROM EXCEL
# ============================================================================

def load_excel_data(dp_file: str, snp_file: str) -> Tuple[Dict, Dict, Dict]:
    """Load data from Excel files"""
    
    logger.info("Loading Excel files...")
    
    # Load DP Shortage data
    df_headers = pd.read_excel(dp_file, sheet_name="DP Shortage", header=None, skiprows=18, nrows=4, usecols=range(14, 135))
    product_headers = {}
    for col_idx in range(df_headers.shape[1]):
        product_id = normalize_product_no(df_headers.iloc[1, col_idx])
        if product_id and product_id != '0':
            product_headers[product_id] = {
                'Product_ID': product_id,
                'Product_Description': normalize_text(df_headers.iloc[3, col_idx]),
                'Batch_Size': df_headers.iloc[0, col_idx],
                'Column_Index': col_idx + 14
            }
    
    # Load materials
    df_materials = pd.read_excel(dp_file, sheet_name="DP Shortage", header=None, skiprows=22, nrows=520, usecols=[0, 1, 2, 3, 4, 5, 10, 13])
    df_materials.columns = ['Material', 'Material_Description', 'Model', 'Product_Family', 'Section', 'Common_Unique', 'Total_Lead_Time', 'BUoM']
    df_materials['Material_Normalized'] = df_materials['Material'].apply(normalize_product_no)
    df_materials_filtered = df_materials[(df_materials['Material_Normalized'].notna()) & (df_materials['Material_Normalized'] != '0')].copy()
    
    # Load quantities
    df_qty = pd.read_excel(dp_file, sheet_name="DP Shortage", header=None, skiprows=22, nrows=520, usecols=range(14, 135))
    qty_col_map = {product_id: info['Column_Index'] - 14 for product_id, info in product_headers.items()}
    
    # Load SKU data
    sku_data = {}
    try:
        df_adv = pd.read_excel(snp_file, sheet_name="Adv Mkt-Mar'25", header=None, skiprows=2, nrows=363, usecols=[1, 3, 5, 8])
        df_adv.columns = ['Product_ID', 'SKU', 'Country', 'Pack_Size']
        for _, row in df_adv.iterrows():
            prod_id = normalize_product_no(row['Product_ID'])
            if prod_id and prod_id not in sku_data:
                sku_data[prod_id] = {
                    'SKU': normalize_text(row['SKU']),
                    'Country': normalize_text(row['Country']),
                    'Pack_Size': row['Pack_Size']
                }
    except Exception as e:
        logger.warning(f"Error loading Adv Mkt data: {e}")
    
    # Load resource data
    resource_data = {}
    try:
        df_resources = pd.read_excel(snp_file, sheet_name="DP Line Utilization", header=None, skiprows=2, nrows=240, usecols=[1, 2, 4])
        df_resources.columns = ['Resource_ID', 'Resource_Description', 'Product_ID']
        for _, row in df_resources.iterrows():
            prod_id = normalize_product_no(row['Product_ID'])
            if prod_id:
                resource_data[prod_id] = {
                    'Resource_ID': normalize_text(row['Resource_ID']),
                    'Resource_Description': normalize_text(row['Resource_Description'])
                }
    except Exception as e:
        logger.warning(f"Error loading Resource data: {e}")
    
    logger.info(f"✓ Loaded {len(product_headers)} products, {len(df_materials_filtered)} materials, {len(sku_data)} SKUs")
    
    return (
        {'headers': product_headers, 'materials': df_materials_filtered, 'qty': df_qty, 'qty_col_map': qty_col_map},
        sku_data,
        resource_data
    )

# ============================================================================
# DATA INSERTION INTO MEMSQL
# ============================================================================

def insert_materials(connector: MemSQLConnector, materials_df: pd.DataFrame):
    """Insert materials into MemSQL"""
    logger.info("Inserting materials...")
    
    insert_query = """
        INSERT INTO materials 
        (material_id, material_code, material_description, section, common_unique, 
         total_lead_time_weeks, buom, model) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            material_description = VALUES(material_description),
            updated_at = CURRENT_TIMESTAMP
    """
    
    data = []
    for _, row in materials_df.iterrows():
        material_id = row['Material_Normalized']
        data.append((
            material_id,
            row['Material_Normalized'],
            normalize_text(row['Material_Description']),
            normalize_text(row['Section']),
            normalize_text(row['Common_Unique']),
            float(row['Total_Lead_Time']) if pd.notna(row['Total_Lead_Time']) else None,
            normalize_text(row['BUoM']),
            extract_model_components(row['Model'])
        ))
    
    count = connector.executemany_query(insert_query, data)
    logger.info(f"✓ Inserted {count} materials")
    connector.commit()

def insert_products(connector: MemSQLConnector, product_headers: Dict, resource_data: Dict):
    """Insert products into MemSQL"""
    logger.info("Inserting products...")
    
    insert_query = """
        INSERT INTO products 
        (product_id, product_code, product_description, product_family, hierarchy_level, bom_type, batch_size) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            product_description = VALUES(product_description),
            updated_at = CURRENT_TIMESTAMP
    """
    
    data = []
    for product_id, info in product_headers.items():
        data.append((
            product_id,
            product_id,
            normalize_text(info.get('Product_Description', 'N/A')),
            'N/A',  # Will be populated from hierarchy
            'Packing' if str(product_id).startswith('8') else 'Assembly' if str(product_id).startswith('700003') else 'Filling',
            'Standard',
            info.get('Batch_Size', 'N/A')
        ))
    
    count = connector.executemany_query(insert_query, data)
    logger.info(f"✓ Inserted {count} products")
    connector.commit()

def insert_skus(connector: MemSQLConnector, sku_data: Dict, hierarchy_mapping: Dict):
    """Insert SKUs into MemSQL"""
    logger.info("Inserting SKUs...")
    
    insert_query = """
        INSERT INTO skus 
        (sku_id, sku_code, sku_description, product_family, pack_size, country, region, 
         assembly_product_id, filling_product_id) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            updated_at = CURRENT_TIMESTAMP
    """
    
    data = []
    for sku_code, info in sku_data.items():
        mapping = hierarchy_mapping.get(sku_code, {})
        data.append((
            sku_code,
            sku_code,
            normalize_text(info.get('SKU', 'N/A')),
            mapping.get('family', 'N/A'),
            info.get('Pack_Size', 'N/A'),
            normalize_text(info.get('Country', 'N/A')),
            'N/A',  # Region
            mapping.get('assembly', None),
            mapping.get('filling', None)
        ))
    
    count = connector.executemany_query(insert_query, data)
    logger.info(f"✓ Inserted {count} SKUs")
    connector.commit()

def insert_bom_hierarchy(connector: MemSQLConnector, pegging_data: List[Dict]):
    """Insert BOM hierarchy into MemSQL"""
    logger.info("Inserting BOM hierarchy...")
    
    insert_query = """
        INSERT INTO bom_hierarchy 
        (sku_id, level, product_id, product_description, material_id, material_description, 
         quantity, section, common_unique, buom, lead_time_weeks, resource_id, resource_description) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    data = []
    for record in pegging_data:
        level = 1 if record.get('BOM_Level') == 'L1_Market_SKU' else 2 if record.get('BOM_Level') == 'L2_Assembly' else 3
        data.append((
            record.get('SKU'),
            level,
            record.get('Product_ID'),
            record.get('Product_Description'),
            record.get('Material'),
            record.get('Material_Description'),
            float(record.get('QTY', 0)) if is_valid_qty(record.get('QTY')) else 0,
            record.get('Section'),
            record.get('Common_Unique'),
            record.get('BUoM'),
            float(record.get('Total_Lead_Time', 0)) if pd.notna(record.get('Total_Lead_Time')) else None,
            record.get('Resource_ID'),
            record.get('Resource_Description')
        ))
    
    count = connector.executemany_query(insert_query, data)
    logger.info(f"✓ Inserted {count} BOM hierarchy records")
    connector.commit()

def insert_resources(connector: MemSQLConnector, resource_data: Dict):
    """Insert resources into MemSQL"""
    logger.info("Inserting resources...")
    
    insert_query = """
        INSERT INTO resources 
        (resource_id, resource_description, molecule, product_id, stage) 
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            updated_at = CURRENT_TIMESTAMP
    """
    
    data = []
    for product_id, info in resource_data.items():
        data.append((
            info.get('Resource_ID', 'N/A'),
            info.get('Resource_Description', 'N/A'),
            'N/A',  # Molecule
            product_id,
            'Assembly' if '700003' in str(product_id) else 'Filling' if '700001' in str(product_id) else 'Packing'
        ))
    
    count = connector.executemany_query(insert_query, data)
    logger.info(f"✓ Inserted {count} resources")
    connector.commit()

def insert_routing_rules(connector: MemSQLConnector, routing_rules: Dict):
    """Insert routing rules into MemSQL"""
    logger.info("Inserting routing rules...")
    
    insert_query = """
        INSERT INTO routing_rules 
        (rule_id, rule_description, resource_id, rule_type, stage, priority, is_active) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            updated_at = CURRENT_TIMESTAMP
    """
    
    data = []
    for rule_id, info in routing_rules.items():
        data.append((
            rule_id,
            info.get('Description', ''),
            info.get('Resource', ''),
            info.get('Type', ''),
            info.get('Stage', ''),
            1,
            True
        ))
    
    count = connector.executemany_query(insert_query, data)
    logger.info(f"✓ Inserted {count} routing rules")
    connector.commit()

# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================

def main():
    """Main orchestration function"""
    
    logger.info("="*100)
    logger.info("MATERIAL PEGGING TO MEMSQL - STARTING PROCESS")
    logger.info("="*100)
    
    # File paths
    dp_file = "/home/supriyo/Downloads/Biocon_nw/20251006-DP Material Shortage - Working file.xlsx"
    snp_file = "/home/supriyo/Downloads/Biocon_nw/ParkourSC_SNP.xlsx"
    
    # Hierarchy mapping (same as before)
    product_mapping = {
        '800004403': {'assembly': '700003964', 'filling': '700001012', 'family': 'Glargine_mCB_DLP'},
        '800006506': {'assembly': '700004129', 'filling': '700004130', 'family': 'Glargine_sMCB_DLP_EU'},
        '800004400': {'assembly': '700001123', 'filling': '700001123', 'family': 'Glargine_Vial'},
        # ... add all mappings
    }
    
    # Routing rules
    routing_rules = {
        'C1': {'Description': 'Pack 1/10 → Manual Pack', 'Resource': 'MFMPPL012702001', 'Type': 'Low volume', 'Stage': 'Packing'},
        'C2': {'Description': 'Pack 5 DLP → Assembly + Auto Pack', 'Resource': 'BIB03/BIB05', 'Type': 'High volume', 'Stage': 'Assembly'},
        # ... add all rules
    }
    
    try:
        # Step 1: Load Excel data
        logger.info("\nStep 1: Loading Excel files...")
        bom_data, sku_data, resource_data = load_excel_data(dp_file, snp_file)
        
        # Step 2: Connect to MemSQL
        logger.info("\nStep 2: Connecting to MemSQL...")
        connector = MemSQLConnector(MEMSQL_CONFIG)
        if not connector.connect():
            logger.error("Failed to connect to MemSQL")
            return False
        
        # Step 3: Create tables
        logger.info("\nStep 3: Creating tables...")
        if not create_tables(connector):
            logger.error("Failed to create tables")
            connector.close()
            return False
        
        # Step 4: Insert data
        logger.info("\nStep 4: Inserting data...")
        
        insert_materials(connector, bom_data['materials'])
        insert_products(connector, bom_data['headers'], resource_data)
        insert_skus(connector, sku_data, product_mapping)
        insert_resources(connector, resource_data)
        insert_routing_rules(connector, routing_rules)
        
        logger.info("\n" + "="*100)
        logger.info("✓ MATERIAL PEGGING TO MEMSQL - COMPLETED SUCCESSFULLY")
        logger.info("="*100)
        
        connector.close()
        return True
        
    except Exception as e:
        logger.error(f"Fatal Error: {e}", exc_info=True)
        connector.rollback()
        connector.close()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)