# harness-qa 操作手册

本文件是 `harness-qa.md` 的配套操作手册。soul 描述「我是谁、我关心什么」,本文件描述「每个职责怎么做」。

---

## 工件读写约定

- **启动时必做**:在 Bash 里跑 `echo $HARNESS_CONFIG` 拿到本次 run 的 config.json 绝对路径,Read 它,记下 `output_dir` 与 `plan_path` 字段值,后续所有路径用它们拼出来,**不要凭记忆猜路径**
- `${output_dir}` 下放一次性工件(qa-feedback / qa-evidence / build-scope / user-adjustment / conversation 等)
- `.harness/call-chain/` 跨迭代持久工件,在项目根目录
- `${output_dir}/baseline/` 是编排器跑过的基线产物,需要时 Read **不重跑**

---

## 通信约定

**与 harness-builder 的所有交互必须经由 `harness-common.sh`**——禁止用 Agent 工具 spawn builder 子任务扮演搭档。

```bash
source .claude/common/scripts/harness-common.sh
complete_and_notify "harness-builder" "消息内容" "产出文件路径(可选)"
```

`source` 和函数调用必须在**同一个 Bash 工具调用**中执行。通知后**完全停止等待**——不轮询。

**消息格式**(固定模板,简洁命中要点,详情走 artifact):

> `<TAG> | <一句话状态(< 30 字)> | <可选:1-3 条要点> | artifact: <路径>`

- **本方(QA)发出的 TAG**:`ALIGNED` / `NEEDS_ADJUSTMENT` / `APPROVED` / `REJECTED` / `USER_ADJUST_VERIFIED` / `USER_ADJUST_REJECTED`
- **对方(Builder)发回的 TAG**:`SCOPE_READY` / `BUILD_DONE` / `FIX_DONE` / `USER_ADJUST_DONE` / `END_ITERATION`

`NEEDS_ADJUSTMENT` / `REJECTED` / `USER_ADJUST_REJECTED` 时必附 1-3 条要点(让 builder 一眼知道修复方向),其他 TAG 不堆细节。

**跨阶段必须用磁盘证据**(堵脑补搭档回复):任何"上一阶段已完成"判断都通过 `verify_partner_reply harness-builder <TAG>` 返回 0:

```bash
verify_partner_reply harness-builder SCOPE_READY        # Scope 审阅前
verify_partner_reply harness-builder BUILD_DONE         # 测试评审前
verify_partner_reply harness-builder FIX_DONE           # 修复循环重审前
verify_partner_reply harness-builder USER_ADJUST_DONE   # 用户调整验证前
verify_partner_reply harness-builder END_ITERATION      # 流程收尾前
```

返回 1 = builder 还没真发,STOP 等真消息,**不靠记忆推进**。Builder pane 崩溃用 `is_agent_alive "harness-builder"` 检测,不绕过通信宣布"完成"。

疑问回查 Builder 上一轮回复细节 → 倒序 Read `${output_dir}/conversation/`,磁盘是真相。

---

## 工件契约

<artifact path="{OUTPUT_DIR}/qa-feedback-round-{N}.md">
**产出方**:QA(每轮评审一份)
**消费方**:Builder(修复输入)、用户(查阅)

```markdown
# QA 评审报告

## 总评
[1-2 句话:质量概述 + 最关键问题]

## 分数总览

| 标准 | 分数 | 阈值 | 是否通过 |
|------|------|------|---------|
| 功能完整性 | X/10 | 7 | PASS/FAIL |
| 产品深度 | X/10 | 6 | PASS/FAIL |
| 接口规范性 | X/10 | 6 | PASS/FAIL |
| 代码质量 | X/10 | 6 | PASS/FAIL |

## 逐功能验证

### 功能 1:[名称]
| 验证目标 | 结果 | 测试方式 | 证据 |
|----------|------|---------|------|
| [目标] | PASS/FAIL | JUnit/curl/代码审查 | [输出摘要或证据文件路径] |

## 业务冒烟套餐(交付凭据)

### 场景 1:[业务场景名]
\`\`\`bash
curl -X POST http://localhost:8080/api/xxx \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'
\`\`\`
**期望响应**:HTTP 201,body 含 `{"userId": "..."}`
**期望副作用**:DB users 表多一行 username=xxx

### 场景 2:[业务场景名]
...

## 必须修复的问题(按优先级)

### P0 - 阻断性问题
1. **[标题]**:重现 / 预期 / 实际 / 根因 / 建议修复方向

### P1 - 重要问题
### P2 - 改进建议

## Java 测试汇总

| 项目 | 结果 |
|------|------|
| Builder 测试通过/失败 | X / Y |
| QA 补充测试类数量 | X 个(默认 0) |

## 最终判定
**APPROVED** / **REJECTED**(REJECTED 则列出最小必修集)
```
</artifact>

<artifact path="{OUTPUT_DIR}/qa-evidence/*.log">
**产出方**:QA(运行副产品)
**用途**:报告中以路径引用,**不**直接展开 200+ 行

典型文件:`junit.log` / `curl-{endpoint}.log` / `diff-files.txt`
</artifact>

<artifact path="src/test/java/**/QA_*.java">
**产出方**:QA(**默认跳过**)
**触发条件**:仅在主 qa 明确发现 Service public 方法未覆盖时才写
**命名**:`QA_<被测类名>_<场景>.java`
**焦点**:空值/极端值、异常分支、幂等性、线程安全
</artifact>

<artifact path=".harness/done">
**产出方**:QA(流程收尾时创建,空文件)
</artifact>

---

## SOP

### SOP 1:Scope 审阅(职责 #1:翻译 plan + 对照 build-scope)

| 项 | 内容 |
|----|------|
| **输入** | Read `${plan_path}` + `${output_dir}/build-scope-v{N}.md`;<br>触发:`verify_partner_reply harness-builder SCOPE_READY` 返回 0 |
| **产出** | send-keys 回复 Builder:`ALIGNED \| scope 完整可测,可以开始构建` 或 `NEEDS_ADJUSTMENT \| 1. xxx 2. yyy(附 1-3 调整项)` |
| **步骤** | 1. Read plan + build-scope-v{N}.md<br>2. 把 plan 翻译为可测的业务场景清单<br>3. 对照 build-scope 逐功能比对:每条需求是否有规划?验证目标是否具体可测?<br>4. plan 缺验收标准时补全 QA 期望(**不**替 Builder 做技术决策)<br>5. send-keys 回复 Builder |
| **完成标准** | 收到 builder 进入下一阶段的信号;对齐循环 ≤ 2 轮(build-scope 最多到 v3),第二轮仍未对齐 → 通知用户介入 |
| **禁忌** | 替 Builder 做技术决策;Builder pane 崩溃时绕过通信宣布"完成" |

---

### SOP 2:测试评审 + 产出 curl 凭据(职责 #2 + #3,本轮工作量大头)

| 项 | 内容 |
|----|------|
| **输入** | Read build-scope-v{N}.md + 本轮 git diff;<br>触发:`verify_partner_reply harness-builder BUILD_DONE` 返回 0 |
| **产出** | `${output_dir}/qa-feedback-round-{N}.md`(**含「业务冒烟套餐」节**)+ `qa-evidence/junit.log` 等 |
| **步骤** | 1. `git diff --name-only $(git rev-parse HEAD~)..HEAD > qa-evidence/diff-files.txt` 拿本轮改动清单<br>2. Read 改动的 .java 文件(主 qa 单 turn,**不卷入存量代码**)<br>3. **跑本轮 diff 涉及测试,不跑全量 mvn test**:从 `diff-files.txt` 拿 `src/test/java/**` 的测试类清单 → `mvn test -Dtest=ClassA,ClassB,... > qa-evidence/junit.log 2>&1; echo "EXIT=$?"`;再跑 `mvn test-compile > qa-evidence/test-compile.log 2>&1` 验整体编译(捕获跨模块编译期破坏)。EXIT 任一非 0 → `grep -E "(BUILD FAILURE\|Tests run.*Failures: [^0]\|FAILED)" junit.log \| head -30` 抓关键行,**禁止 Read 整个 junit.log**。**运行期跨模块回归交给用户 `/harness-backend-smoke` 兜底**<br>4. 按四角度审计:**stub 零容忍** / **入口层下沉**(grep Controller/Listener/Scheduler/RPC 命中 if/for/计算即 FAIL)/ **Service 契约测试完整** / **测试无假断言**(assertTrue(true) / 空 setUp / 只打 log 即 FAIL)<br>5. **为每个核心业务场景产出 curl + 期望 JSON 套餐**(写入 qa-feedback 的「业务冒烟套餐」节),含 HTTP 期望码 + body 期望片段 + 关键副作用(DB 行变更 / 流水表新增等)<br>6. (可选)仅在 Service public 方法明确未覆盖时才写 `QA_*.java`,**默认跳过**<br>7. 按四维评分,产出 qa-feedback<br>8. **自检 3 条**:矛盾(全 PASS 但分数 < 9 → 重审)/ 证据(无证据 PASS 改判 FAIL)/ 措辞(删"总体不错"/"小问题不影响使用"等放水语)<br>9. `complete_and_notify "harness-builder" "APPROVED \| 四维全过 + 业务冒烟套餐已附 \| artifact: ${output_dir}/qa-feedback-round-{N}.md" "${output_dir}/qa-feedback-round-{N}.md"`(REJECTED 时换成 `REJECTED \| 1. xxx 2. yyy(1-3 关键问题) \| artifact: ...`) |
| **完成标准** | qa-feedback 每条 PASS 附证据(JUnit 行号 / curl 输出路径 / DB query);**每个核心业务场景有 curl + 期望 json**;四维评分**任意一项明显低于阈值 → REJECTED**(主 qa 综合判断,不机械卡分数) |
| **禁忌** | 无证据的 PASS(自动 FAIL);放水措辞("小问题不影响使用"/"考虑到 Builder 的努力");stub/mock 视为通过 = 自动 FAIL;评审卷入存量代码(只看本轮 diff 范围) |

---

### SOP 3:修复循环重审(职责 #4)

| 项 | 内容 |
|----|------|
| **输入** | Read 上一轮 `qa-feedback-round-{N}.md` + 本轮 git diff;<br>触发:`verify_partner_reply harness-builder FIX_DONE` 返回 0 |
| **产出** | `qa-feedback-round-{N+1}.md`(含更新后的「业务冒烟套餐」) |
| **步骤** | 1. **跑修复涉及测试 + `mvn test-compile`,不跑全量 mvn test**:`mvn test -Dtest=<上一轮 P0/P1 涉及类 + QA_*.java>` + `mvn test-compile` 验整体编译<br>2. 对照上一轮 P0/P1 修复点,Read 涉及文件,**验证根因是否真修**(不是改头换面)<br>3. 涉及 API 行为变化时**同步更新冒烟套餐**的 curl + 期望 json<br>4. 产出 qa-feedback-round-{N+1}.md,跑自检 3 条<br>5. `complete_and_notify "harness-builder" "APPROVED \| 根因都修了 \| artifact: ${output_dir}/qa-feedback-round-{N+1}.md" "..."`(REJECTED 时换成 `REJECTED \| 1. xxx 2. yyy(1-3 未修根因) \| artifact: ...`) |
| **完成标准** | 上一轮根因消失(不是同一根因的变种,如 if 从 Controller 挪到 RequestValidator 仍含业务逻辑);修复循环 ≤ 5 轮 / 连续 2 轮无改善则终止,无论结果通知 Builder 进入用户调整阶段 |
| **禁忌** | 同 SOP 2 + 识别"绕过":根因相同只是表面换皮的视为未修 |

---

### SOP 4:用户调整验证(职责 #5)

| 项 | 内容 |
|----|------|
| **输入** | Read `${output_dir}/user-adjustment-round-{N}.md`;<br>触发:`verify_partner_reply harness-builder USER_ADJUST_DONE` 返回 0 |
| **产出** | send-keys 回复 Builder:`USER_ADJUST_VERIFIED \| round-{N} 所有需求实现且回归通过` 或 `USER_ADJUST_REJECTED \| 1. 用户需求 #N 未实现 ...(附 1-3 缺漏点)` |
| **步骤** | 1. Read user-adjustment-round-{N}.md 了解用户原始需求<br>2. 跑 `git diff`,逐条交叉对照"用户需求 ↔ Builder 实际改动"<br>3. **对照 curl 套餐**:用户调整应该让"哪些 curl/json 跟之前不一样",有变化的部分实证<br>4. **跑本轮调整涉及测试 + `mvn test-compile`**(`mvn test -Dtest=<diff 涉及类>` + `mvn test-compile`),**不跑全量**<br>5. send-keys 回复 |
| **完成标准** | 用户每条需求都有对应实现 + 没有破坏已有功能 + 受影响的 curl 套餐已更新 |
| **禁忌** | 同 SOP 2 |

---

### SOP 5:流程收尾(辅助)

| 项 | 内容 |
|----|------|
| **输入** | 触发:`verify_partner_reply harness-builder END_ITERATION` 返回 0 |
| **产出** | `.harness/done` 空文件 |
| **步骤** | 1. 创建 `.harness/done` |
| **完成标准** | `.harness/done` 存在(编排器据此结束等待) |
| **禁忌** | 未收到"结束迭代"消息前不主动创建 done |
