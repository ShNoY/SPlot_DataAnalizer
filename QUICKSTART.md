# 🚀 SPlot DataAnalyzer - 実行ガイド

## クイックスタート

### 1. アプリケーション起動

```bash
cd c:\Users\xc100753\py_envs
python Splot2.py
```

またはレガシー互換性スクリプト:
```bash
python Splot3.py  # Splot2.pyと同じ
```

### 2. Formula機能の使用

#### a) Formula Managerを開く
1. ツールバーの **「Formula Mgr」** ボタンをクリック
2. Formula Manager ダイアログが開く

#### b) 新しい数式を追加
1. 「Add...」ボタンをクリック
2. FormulaEditDialog で以下を入力:
   - **Result Name**: 計算結果の変数名（例: `Power`）
   - **Unit**: 単位（例: `W`）
   - **Expression**: Python式（例: `Voltage * Current`）
3. 利用可能な変数リストから変数をクリックして挿入
   - 日本語変数（括弧付き）例：`ダイナモトルク[P]` → 自動的に `var_0` に変換
4. **OK** をクリック

#### c) 数式を計算・適用
1. ファイルを読み込む
2. Formula Manager で **「Apply All Formulas」** をクリック
3. 計算結果が Data Browser に青色で表示

#### d) 数式をエクスポート・インポート
- **Export**: 「Export Formulas (JSON)」→ 他のプロジェクトで再利用可能
- **Import**: 「Import Formulas (JSON)」→ 過去のformulas.jsonを読み込み

## 主な機能

### ✅ データインポート
- CSV（エンコーディング・区切り文字選択可）
- Excel（行構造選択可）
- TSV（エンコーディング選択可）
- JSON

### ✅ Formula機能
- 数式定義・編集・削除
- JSON自動保存・読み込み
- 日本語変数対応（括弧付き）
- リアルタイムプレビュー

### ✅ 可視化
- 複数グラフの同時表示
- 軸ラベルの日本語対応
- X軸リンク機能

### ✅ データ管理
- データブラウザ検索
- トレース（グラフ）の個別設定
- スケーリング・変換機能

## ファイル構成

| ファイル | 説明 | 行数 |
|---------|------|------|
| `Splot2.py` | **メインアプリケーション** | 2443 |
| `formula_extension.py` | **Formula機能モジュール** | 516 |
| `Splot3.py` | レガシーラッパー（互換性） | 29 |
| `import_manager.py` | データインポート系 | 621 |
| `formulas.json` | 保存済み数式（自動） | - |

## アーキテクチャの新設計

### 旧設計 ❌
```
Splot3.py (Complex)
  └─ extends Splot2.py (2430 lines)
```

### 新設計 ✅
```
Splot2.py (Main)
  ├─ FormulaManagerMixin (formula_extension.py)
  └─ QMainWindow
```

**メリット**:
- コード責任の明確化
- 保守性・拡張性の向上
- Splot3が90%コード削減

## トラブルシューティング

### 症状: アプリが起動しない

**確認項目**:
1. Python環境が正しく設定されているか
```bash
C:/Users/xc100753/py_envs/splot_env/Scripts/python.exe --version
```

2. 必要なライブラリがインストール済みか
```bash
python -c "import PyQt6, matplotlib, pandas, xarray"
```

### 症状: Formula機能がない

**確認**:
- Splot2.py を起動したか？（Splot3.py ではない）
- ツールバーの「Formula Mgr」ボタンが見えるか

### 症状: 数式計算エラー

**確認**:
- 変数名が正しいか（Data Browserで確認）
- 日本語変数の場合、括弧部分は自動変換されるので括弧は省略
- 例: `ダイナモトルク[P]` という変数は、式では `var_0` を使用

## よくある質問

### Q1: Splot2.py と Splot3.py の違いは？

**A**: 実質的には同じです。
- `Splot2.py`: 本体（推奨）
- `Splot3.py`: ラッパー（互換性のため提供）

新規ユーザーは Splot2.py を使用してください。

### Q2: 前回保存した数式が読み込まれない

**A**: `formulas.json` を確認:
1. ファイルが存在するか？
   ```bash
   ls -la c:\Users\xc100753\py_envs\formulas.json
   ```
2. Splot2.pyと同じディレクトリか？

### Q3: 複数ファイルで数式を共有したい

**A**: 
1. 最初のファイルで数式を作成・計算
2. Formula Manager → Export Formulas
3. 別のファイルを開く
4. Formula Manager → Import Formulas (先ほどのファイル)

### Q4: Formula計算に時間がかかる

**A**: 大きなデータセットの場合は時間がかかります:
- 「Calc Now」は全数式を実行
- 個別計算の実装は v2.0 予定

## デバッグモード

### コンソール出力を確認
```bash
python Splot2.py 2>&1 | Tee-Object -FilePath debug.log
```

### Formula計算のデバッグ出力
Formula計算時、コンソールに以下のように出力されます:
```
[DEBUG] Expression: ダイナモトルク[P] * 2 -> var_0 * 2
```

これは正常な動作です（括弧付き変数名の正規化処理）。

## 高度な使用方法

### カスタム関数を使用
Formula Expressionで利用可能な組み込み関数:
```python
np.sin()      # NumPy関数
np.sqrt()     # 平方根
abs()         # 絶対値
min(), max()  # 最小値・最大値
pd.rolling()  # Pandas機能（一部）
```

### 条件付き計算
```python
# 例: 温度が20以上の場合だけ計算
np.where(Temperature > 20, Power, 0)
```

### 複合計算
```python
# 例: 複数変数を使用した複雑な計算
(Voltage * Current - Losses) * Efficiency
```

## パフォーマンスチューニング

### 大規模データセット（>100,000行）
1. 不要な数式は削除
2. 複雑な数式は前処理で簡潔に
3. データサンプリングを検討

### 複雑な数式
1. 中間変数を使用して段階計算
2. NumPy 矢量化操作を活用
3. ループは避ける

## 参考ドキュメント

- `ARCHITECTURE.md` - 詳細設計書
- `README_FORMULA_REFACTOR.md` - 再設計ドキュメント
- `IMPORT_MANAGER_GUIDE.md` - インポート機能ガイド

## 次のステップ

1. **基本的な使用**
   - Splot2.py で起動
   - CSVファイルを読み込み
   - 簡単な数式を作成・計算

2. **ステップアップ**
   - 複数グラフを配置
   - Formula を組み合わせる
   - データエクスポート

3. **高度な活用**
   - Excelファイル対応
   - 複雑な数式設計
   - 他ユーザーと数式共有

---

**Version**: v23 + Formula Extension (Refactored)  
**Last Updated**: 2025年12月4日  
**Status**: ✅ Production Ready
