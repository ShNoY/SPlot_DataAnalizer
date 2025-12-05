# Import Manager - 使用ガイド

## 概要

新しい **Import Manager** 機能は、SPlot に拡張可能なデータインポートシステムを追加しました。

### 主な特徴

- ✅ **複数形式対応**: CSV, TSV, Excel (.xlsx), JSON をサポート
- ✅ **文字コード選択可能**: UTF-8, CP932, Shift-JIS, Latin-1, UTF-16
- ✅ **区切り文字選択可能**: カンマ、セミコロン、タブ、パイプ、スペース
- ✅ **自動形式検出**: ファイル拡張子から自動判別
- ✅ **拡張設計**: 新しいデータ形式は import_manager.py に追加するだけで対応可能

---

## 使用方法

### 1. ツールバーから インポート

ツールバーの **Import** ボタンをクリックするとドロップダウンメニューが表示されます。

#### メニューオプション:
- **CSV/DAT Files** - CSV/DAT ファイルをインポート（文字コード・区切り文字選択可）
- **Excel Files** - Excel (.xlsx) ファイルをインポート
- **Tab-Separated Values** - TSV ファイルをインポート（文字コード選択可）
- **JSON Files** - JSON ファイルをインポート
- **Auto Detect (All Formats)** - ファイル拡張子から自動判別してインポート

### 2. CSV インポート時の設定

CSV ファイルを選択するとオプションダイアログが表示されます:

```
CSV Import Options
┌────────────────────────┐
│ Encoding: [utf-8 ▼]    │
│ Delimiter: [,      ▼]  │
└────────────────────────┘
```

**Encoding オプション:**
- utf-8 (推奨 - 英数・日本語)
- cp932 (Windows-31J)
- shift_jis (Shift-JIS)
- latin-1 (西欧言語)
- utf-16 (Unicode)

**Delimiter オプション:**
- `,` (カンマ) - 標準 CSV
- `;` (セミコロン) - ヨーロッパ形式
- `\t` (タブ) - TSV 互換
- `|` (パイプ)
- ` ` (スペース)

### 3. TSV インポート時の設定

TSV ファイルを選択するとオプションダイアログが表示されます:

```
TSV Import Options
┌────────────────────────┐
│ Encoding: [utf-8 ▼]    │
└────────────────────────┘
```

---

## 新しいデータ形式の追加方法

### 例: HDF5 形式対応の追加

**import_manager.py** に以下を追加します:

```python
class HDF5Importer(BaseImporter):
    """HDF5 file importer"""
    
    extension = ".h5"
    description = "HDF5 Files"
    
    def import_file(self, file_path: str, **options) -> Tuple[bool, Optional[xr.Dataset], str]:
        """Import HDF5 file"""
        try:
            ds = xr.open_dataset(file_path)
            return True, ds, ""
        except Exception as e:
            return False, None, str(e)
```

その後、`ImportManager._register_builtin_importers()` に追加:

```python
def _register_builtin_importers(self):
    """Register standard importers"""
    self.register_importer(CSVImporter())
    self.register_importer(ExcelImporter())
    self.register_importer(JSONImporter())
    self.register_importer(TSVImporter())
    self.register_importer(HDF5Importer())  # <- 新規追加
```

### オプション付きカスタムフォーマットの例

NetCDF 形式でオプション付きインポーター:

```python
class NetCDFImporter(BaseImporter):
    """NetCDF file importer with optional engine selection"""
    
    extension = ".nc"
    description = "NetCDF Files"
    
    def import_file(self, file_path: str, **options) -> Tuple[bool, Optional[xr.Dataset], str]:
        """Import NetCDF file"""
        try:
            engine = options.get('engine', 'netcdf4')
            ds = xr.open_dataset(file_path, engine=engine)
            return True, ds, ""
        except Exception as e:
            return False, None, str(e)
    
    def get_options_dialog(self, parent=None) -> Optional[Dict]:
        """Show engine selection dialog"""
        # カスタムダイアログを実装
        return NetCDFImportOptionsDialog.get_options(parent)
```

---

## アーキテクチャ

### クラス構成

```
BaseImporter (ABC)
├── CSVImporter
├── ExcelImporter
├── JSONImporter
├── TSVImporter
└── [カスタムインポーター]

ImportManager (シングルトン)
├── importers: Dict[ext, BaseImporter]
├── register_importer()
├── import_file()
└── get_file_filter()

Options Dialogs
├── CSVImportOptionsDialog
├── TSVImportOptionsDialog
└── [カスタムオプションダイアログ]
```

### 設計パターン

1. **レジストリパターン**: ImportManager がすべてのインポーターを管理
2. **ファクトリパターン**: ファイル拡張子から自動的にインポーターを選択
3. **ストラテジーパターン**: 各形式で異なるインポートロジックを実装
4. **シングルトンパターン**: グローバル ImportManager インスタンス

---

## ファイル構成

### import_manager.py (新規)

- `BaseImporter` - 抽象基盤クラス
- `CSVImporter` - CSV/DAT インポーター
- `ExcelImporter` - Excel インポーター
- `JSONImporter` - JSON インポーター
- `TSVImporter` - TSV インポーター
- `CSVImportOptionsDialog` - CSV オプションダイアログ
- `TSVImportOptionsDialog` - TSV オプションダイアログ
- `ImportManager` - 統合管理クラス
- `get_import_manager()` - グローバルインスタンス取得

### Splot2.py (修正)

**追加メソッド:**
- `import_data()` - 自動形式検出インポート
- `import_data_by_format(ext)` - 形式指定インポート
- `load_dataset_internal(p, ds)` - xarray Dataset をロード

**削除:**
- 古い `load_file_internal()` - ImportManager に統合

**UI 変更:**
- ツールバーの Import ボタン → ドロップダウンメニュー化

---

## 技術仕様

### データ変換パイプライン

```
Input File
    ↓
Importer.import_file(file_path)
    ↓
pandas.DataFrame
    ↓
DataFrame → xarray.Dataset (単位情報を attrs に保存)
    ↓
SPlotApp.load_dataset_internal()
    ↓
file_data_map[filename] = {'ds': Dataset, 'original_path': path}
```

### xarray Dataset 構造

```python
ds = xr.Dataset()
ds['Variable_Name'] = xr.DataArray(
    values,
    coords={'index': df.index},
    dims='index'
)
ds['Variable_Name'].attrs['unit'] = 'unit_string'
```

---

## 既知の制限

- マルチシート Excel: 最初のシートのみをインポート
- JSON: 平坦な構造を想定（ネストされた JSON は未対応）
- 大規模ファイル: 100MB 以上のファイルは動作保証外

---

## トラブルシューティング

### "Unsupported file format" エラー

**原因**: ファイル拡張子が登録されていない

**解決**: import_manager.py に新しいインポーター登録

### 文字化け発生

**原因**: 文字コード設定が誤っている

**解決**: CSV インポートオプションで正しい Encoding を選択
- Windows-31J ファイル → cp932
- Shift-JIS ファイル → shift_jis
- UTF-8 ファイル → utf-8

### 区切り文字が正しく認識されない

**原因**: Delimiter 設定が誤っている

**解決**: CSV インポートオプションで正しい Delimiter を選択

---

## 今後の拡張予定

- [ ] HDF5 形式対応
- [ ] NetCDF 形式対応  
- [ ] Parquet 形式対応
- [ ] ドラッグ＆ドロップ インポート
- [ ] バッチインポート（複数ファイル一括）
- [ ] データプレビュー機能

