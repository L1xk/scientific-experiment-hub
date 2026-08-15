"""Workbook schemas and conservative column aliases."""

from __future__ import annotations

from typing import Dict, List, Set


SUPPORTED_EXTENSIONS: Set[str] = {".xlsx", ".xlsm", ".csv", ".tsv"}

DATABASE_SHEETS: Dict[str, List[str]] = {
    "Experiment_Index": [
        "Experiment_ID", "Project_ID", "Experiment_Family", "Experiment_Type",
        "Experiment_Name", "Experiment_Date", "Operator", "Objective", "Hypothesis",
        "Sample_Type", "Key_Variable", "Control_Group", "Status", "Outcome",
        "Source_File", "Organized_File", "File_SHA256", "Import_Date", "Data_Version",
        "Metadata_Completeness", "QA_HIGH", "QA_MEDIUM", "QA_LOW", "Notes",
    ],
    "Experiment_Conditions": [
        "Experiment_ID", "Sample_ID", "Group", "Treatment", "Substrate", "Enzyme",
        "Strain", "Gene", "Plasmid", "Concentration", "Temperature", "pH",
        "Reaction_Time", "Culture_Time", "OD600", "Medium", "Carbon_Source",
        "Inducer", "Reaction_Volume", "Biological_Replicate", "Technical_Replicate",
        "Source_Sheet", "Source_Row", "Notes",
    ],
    "Raw_Data": [
        "Record_ID", "Experiment_ID", "Sample_ID", "Group", "Biological_Replicate",
        "Technical_Replicate", "Metric", "Raw_Value", "Unit", "Outlier_Flag",
        "Source_File", "Source_Sheet", "Source_Row", "Source_Column", "Import_Date",
        "Data_Version", "Notes",
    ],
    "Normalized_Data": [
        "Record_ID", "Experiment_ID", "Sample_ID", "Group", "Biological_Replicate",
        "Technical_Replicate", "Metric", "Raw_Value", "Cleaned_Value",
        "Normalized_Value", "Analysis_Value", "Unit", "Transformation",
        "Transformation_Reason", "Outlier_Flag", "Data_Version", "Notes",
    ],
    "Summary": [
        "Experiment_ID", "Group", "Sample_ID", "Metric", "Unit", "Observed_N",
        "Biological_N", "Technical_Aggregation", "Mean", "Median", "SD", "SEM",
        "Min", "Max", "CV_Percent", "Inference_Eligible", "Notes",
    ],
    "Experiment_Knowledge": [
        "Experiment_ID", "Objective", "Observation", "Problem", "Possible_Cause",
        "Conclusion", "Optimization_Idea", "Next_Experiment", "Evidence_Level", "Updated_At",
    ],
    "Cross_Experiment_Comparison": [
        "Experiment_Family", "Metric", "Unit", "Experiment_Count", "First_Date",
        "Latest_Date", "Historical_Mean", "Best_Value", "Best_Experiment_ID",
        "Metric_Direction", "Reproducibility_Status", "Notes",
    ],
    "QA_QC": [
        "Issue_ID", "Experiment_ID", "Severity", "Category", "Message",
        "Source_Sheet", "Source_Row", "Source_Column", "Suggested_Action",
        "Detected_At", "Resolved", "Resolution_Notes",
    ],
    "Data_Conflicts": [
        "Conflict_ID", "Experiment_ID", "Sample_ID", "Metric",
        "Biological_Replicate", "Technical_Replicate", "Existing_Value", "New_Value",
        "Existing_Source", "New_Source", "Detected_At", "Status", "Resolution",
    ],
    "Import_Log": [
        "Import_ID", "Experiment_ID", "Source_File", "File_SHA256", "Import_Date",
        "Data_Version", "Status", "Raw_Archive", "Organized_File", "Message",
    ],
    "Family_Rules": [
        "Rule_ID", "Priority", "Project_ID", "Required_Terms", "Optional_Terms",
        "Excluded_Terms", "Experiment_Family", "Confidence", "Active", "Notes",
    ],
    "Data_Dictionary": ["Sheet", "Field", "Meaning", "Type", "Required", "Allowed_or_Example"],
}

INDEX_HEADERS = [
    "Experiment_ID", "Experiment_Date", "Experiment_Nature", "Experiment_Family",
    "Project_ID", "Status", "Outcome", "Original_File", "Raw_Archive",
    "Organized_File", "File_SHA256", "Import_Date", "Data_Version",
    "Metadata_Completeness", "QA_HIGH", "QA_MEDIUM", "QA_LOW", "Notes",
]

METADATA_LABELS = {
    "experiment_date": {"experiment date", "date", "实验日期", "日期", "实验时间"},
    "experiment_name": {"experiment name", "实验名称", "实验名", "实验性质", "experiment type"},
    "project_id": {"project id", "项目编号", "项目id", "项目"},
    "operator": {"operator", "实验人员", "操作者", "操作人员"},
    "objective": {"objective", "实验目的", "目的"},
    "family": {"experiment family", "实验家族", "实验系列"},
    "batch": {"batch", "batch id", "批次", "批次号"},
}

COLUMN_ALIASES = {
    "sample_id": {"sample", "sample id", "sample_id", "样品", "样品编号", "样本", "样本编号"},
    "group": {"group", "组别", "实验组", "处理组"},
    "treatment": {"treatment", "处理", "处理条件"},
    "biological_replicate": {"biological replicate", "biological_replicate", "bio replicate", "bio_rep", "生物学重复", "生物重复"},
    "technical_replicate": {"technical replicate", "technical_replicate", "tech replicate", "tech_rep", "技术重复"},
    "metric": {"metric", "指标", "检测指标", "parameter", "measurement"},
    "value": {"value", "raw value", "raw_value", "数值", "结果", "measurement value"},
    "unit": {"unit", "单位"},
    "substrate": {"substrate", "底物"},
    "enzyme": {"enzyme", "酶"},
    "strain": {"strain", "菌株"},
    "gene": {"gene", "基因"},
    "plasmid": {"plasmid", "质粒"},
    "concentration": {"concentration", "浓度"},
    "temperature": {"temperature", "temp", "温度"},
    "ph": {"ph", "p h"},
    "reaction_time": {"reaction time", "反应时间"},
    "culture_time": {"culture time", "培养时间"},
    "od600": {"od600", "od 600"},
    "medium": {"medium", "培养基"},
    "carbon_source": {"carbon source", "碳源"},
    "inducer": {"inducer", "诱导剂"},
    "reaction_volume": {"reaction volume", "反应体积"},
}

CONDITION_FIELDS = [
    "sample_id", "group", "treatment", "substrate", "enzyme", "strain", "gene",
    "plasmid", "concentration", "temperature", "ph", "reaction_time", "culture_time",
    "od600", "medium", "carbon_source", "inducer", "reaction_volume",
    "biological_replicate", "technical_replicate",
]

NATURE_KEYWORDS = [
    (("enzyme screening", "酶筛选", "酶活筛选"), "酶筛选实验"),
    (("ph optimization", "ph优化", "ph 优化"), "pH优化实验"),
    (("temperature optimization", "温度优化"), "温度优化实验"),
    (("substrate optimization", "底物优化"), "底物优化实验"),
    (("time course", "时间梯度", "时间过程"), "时间梯度实验"),
    (("fermentation", "发酵"), "发酵实验"),
    (("expression", "表达验证", "蛋白表达"), "表达验证实验"),
]

DATA_DICTIONARY_ROWS = [
    ("Experiment_Index", "Experiment_ID", "Stable experiment identifier", "Text", "Yes", "EXP-YYYYMMDD-XXX"),
    ("Experiment_Index", "Experiment_Date", "Experiment date; import date is never substituted silently", "Date", "Recommended", "YYYY-MM-DD or Unknown"),
    ("Raw_Data", "Raw_Value", "Value copied from the source without cleaning or unit conversion", "Any", "Yes", "Original cell value"),
    ("Raw_Data", "Biological_Replicate", "Independent biological replicate identifier", "Text", "Recommended", "B1, B2, B3 or Unknown"),
    ("Raw_Data", "Technical_Replicate", "Repeated measurement within a biological replicate", "Text", "Optional", "T1, T2, T3 or Unknown"),
    ("Normalized_Data", "Transformation", "Exact transformation formula or operation", "Text", "When transformed", "Technical mean; unit conversion"),
    ("QA_QC", "Severity", "Impact level of a detected quality issue", "Category", "Yes", "HIGH, MEDIUM, LOW"),
    ("Data_Conflicts", "Status", "Conflict resolution status", "Category", "Yes", "OPEN, RESOLVED, VERSIONED"),
]
