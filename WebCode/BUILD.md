# 本地构建

在项目根目录运行：

```powershell
python build.py
```

输出入口是 `Output/index.html`。`WebCode/templates/` 已改为包含
`{{ placeholder }}` 的构建模板，请预览生成页面，而不是直接打开模板。
脚本以自身所在目录定位项目，从其他工作目录调用也可以。

## 环境与依赖

需要 Python 3.10+ 和 Pandoc。Python 构建代码本身只使用标准库。
脚本依次寻找 `--pandoc` 指定的程序、PATH 中的 Pandoc、项目 `.venv`
中 `pypandoc_binary` 附带的 Pandoc，以及当前 Python 环境中的 pypandoc。

如果没有单独安装 Pandoc，可在 Windows PowerShell 中执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
python build.py
```

Linux/macOS 安装方式相同，将安装命令中的解释器路径换为
`.venv/bin/python`。也可以直接安装 Pandoc。

当前项目已安装的本地 `.venv` 可直接用于构建，不必重复安装。
`.venv` 不进入版本控制，服务器只需部署生成文件，无需安装这些构建工具。

## 预览和检查

```powershell
# 构建并启动本地静态预览；Ctrl+C 停止
python build.py --serve

# 更换端口
python build.py --serve --port 8080

# 执行转换和检查，但不更新 Output
python build.py --check

# 将未配置、未列入元数据和空正文等警告视为错误
python build.py --strict

# 回归测试（需要 Pandoc）
python -m unittest discover -s WebCode/tests -v
```

默认预览地址：`http://127.0.0.1:8000/`。预览仅绑定本机；修改源文件后
重新运行构建并刷新浏览器。没有自动监听，也没有生产应用服务器。

## 内容发现与元数据

根目录下的非隐藏目录被当作分类，排除 `WebCode`、`Output`、`__pycache__`。
每个分类只使用分类根目录中的一个 `meta.json`，课程（或日记月份）和章节信息
都集中写在该文件中：

```json
{
  "title": "Math",
  "order": 1,
  "description": "这里填写首页 Math 卡片的文字",
  "subjects": [
    {
      "directory": "M01-LinearAlgebra",
      "title": "线性代数",
      "order": 2,
      "chapters": [
        {"order": 1, "file": "00-introduction.tex", "title": "导言"},
        {"order": 2, "file": "01-matrices.tex", "title": "矩阵"}
      ]
    }
  ]
}
```

- `description` 是首页大类卡片下由你填写的文字；空字符串不会生成说明段落。
- `directory` 指向分类下的英文科目目录。
- 课程与章节按各自的 `order` 升序排列，不根据文件编号或数组位置推断顺序。
- `file` 是同目录下的英文 `.tex` 文件名，保留编号，不允许跳出课程目录。
- `title` 只影响显示文字，不改变生成路径。
- 同一分类内课程的 `order`、同一课程内章节的 `order` 不能重复。
- 多篇课程使用手风琴目录，当前课程默认展开；单篇课程直接链接到文章。
- 左侧只展示当前分类下的课程与章节，不显示“返回首页”“内容目录”、分类名称或数量。
- 缺少分类级 `meta.json` 的分类不会生成内容，并给出警告。
- 科目和月份目录中不允许再放置 `meta.json`；构建会提示将其合并到分类文件。
- 当前分类顺序由各分类根目录的 `meta.json` 明确规定：Math、Crypto、
  Project、Research、Tool、Diary。顶部导航和首页卡片共用这一顺序。
- 正文内小节目录从转换后的标题生成；课程和章节导航只使用元数据。

线性代数以及 `Diary/2026-08`、`Diary/2026-09` 已分别登记在 `Math/meta.json`
和 `Diary/meta.json` 中。新增日记月份时，在 `Diary/meta.json` 的 `subjects`
中增加一项，并在 `chapters` 中引用当月的 `.tex` 文件；月份 `order` 使用如
`202608` 的年月整数。Diary 会按
`order` 倒序排列，因此时间较新的月份会同时出现在分类卡片和文章页左侧目录前面。
只有一个文件的月份在左侧目录中直接显示链接，不出现展开按钮。
未登记的课程和日记目录会逐项警告并跳过；不会猜测标题或自动创建元数据。
元数据未列出的 `.tex` 文件也会警告。
`.md` 不属于本版构建入口。

`01-matrices.tex` 目前没有正文，默认生成“本章内容尚在整理中”的占位页并警告。
`--strict` 会阻止上述情况更新输出。无效 JSON、字段类型错误、重复排序、
不存在的源文件或转换失败，无论是否严格模式都会停止构建。

## 输出与公式

```text
Output/
├── index.html
├── css/
├── assets/
├── Math/
│   ├── index.html
│   └── M01-LinearAlgebra/
│       ├── index.html
│       ├── 00-introduction.html
│       └── 01-matrices.html
└── .build-manifest.json
```

每个分类、课程都有索引页。页面使用相对链接，可部署到静态目录或站点子路径。
分类首页复用网站首页的 Hero 和卡片模板：Hero 标题显示分类名，卡片自动显示
该分类下的科目或日记月份，并链接到相应的第一篇文章。主页分类卡片和顶部导航
同样自动生成；既有分类图标继续使用已有资源。

每个分类根目录下都有一个 `icon/` 目录，用于保存该分类中不同科目或月份卡片
使用的独立图标：

```text
Math/icon/
Crypto/icon/
Project/icon/
Research/icon/
Tool/icon/
Diary/icon/
```

科目图标按对应科目的 `order` 数字命名。例如，`order` 为 `5` 的科目使用
`icon/5.svg`。构建时会把图标复制到分类输出目录，并在分类首页的对应卡片中使用。
如果某个科目尚未提供相应 SVG，构建会继续使用该大类的默认图标。

LaTeX 由 [Pandoc](https://pandoc.org/MANUAL.html) 转为 HTML，公式保留为 TeX，
由 [MathJax](https://docs.mathjax.org/en/v3.2/web/components/index.html) 渲染。
仅有公式的页面加载脚本，默认使用固定版本 `3.2.2` 的 CDN，因此公式渲染需要联网。
如需完全本地化，把完整 MathJax 分发资源放到 `WebCode/assets/` 下，再指定：

```powershell
python build.py --mathjax-url assets/vendor/mathjax/es5/tex-svg.js
```

脚本不会自行下载 MathJax；本地路径相对于 `Output`，会转换为各页的相对 URL。
MathJax 扩展需要保留原分发目录结构。

支持 Pandoc 可解析的标题、段落、列表、代码、表格、图片及文内引用。
引用的本地图片与 PDF 附件会复制到对应课程输出目录；图片建议使用
PNG、JPEG、SVG 等浏览器格式，不能直接用 PDF 当图片。
所有本地资源引用必须限制在课程目录内。网页链接可使用 HTTP(S) 或 mailto。

这不是完整的 TeX 编译器：未知命令、未处理的原始 TeX 和 Pandoc 警告会报错，
不会悄悄删除内容。转换以 Pandoc 沙箱运行，不执行 TeX 或 shell 命令；
需要外部读取的 `\input` / `\include`、复杂宏包或特殊环境可能需要后续单独适配。

## 输出保护

构建先在临时目录中完成转换，检查本地页面链接、锚点与 CSS 资源，成功后才更新输出。
内容错误或严格模式检查失败不会改动原有 `Output`。
构建清单记录脚本生成的文件，后续构建仅清理清单中的过期文件，保留其他文件。
遇到与已有未管理文件同名的输出时会报错，不会直接覆盖。
不要手改生成文件；应修改 `.tex`、元数据或模板后重新构建。

备案入口保留在两个模板的页脚中；实际备案号尚未提供，当前显示“ICP备案”。
