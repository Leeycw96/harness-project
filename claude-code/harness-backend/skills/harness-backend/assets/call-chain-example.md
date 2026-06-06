```xml
<?xml version="1.0" encoding="UTF-8"?>
<!--
  ================================================================================
  【Lifecycle Template】业务生命周期入口清单（端到端测试数据源）
  ================================================================================

  用途：
    本文档作为模板，供开发者/AI 参考后，根据实际项目业务生成对应的
    lifecycle.md 文件。文件中仅列出触发业务新建、流转的全部入口 Java 类
    与外部触达方式，不描述方法级调用链。

  生成规则：
    1. 梳理业务全生命周期，按时间顺序依次排列 step。XML 标签出现的
       先后顺序即为业务流程的执行顺序，不依赖额外的序号属性。
    2. 每个 step 用唯一的 id 标识，供 branch 或外部引用。
    3. 每个 step 标注 entry-type，区分测试脚本可直接触发的类型：
       - "http"      → 测试脚本可直接发 HTTP/Dubbo 请求触发
       - "scheduler" → 由定时任务自动调度触发，测试脚本需 sleep/轮询等待
       - "mq"        → 测试脚本需向指定 Topic 发送 MQ 消息来模拟回调
    4. 若某一步骤存在分支（如审批通过 vs 拒绝），使用 <branch> 节点包裹
       不同的 <path>，并在 path 上标注 trigger="触发条件"。branch 通过
       from-step="某个 step 的 id" 来关联前置步骤。
    5. path 内部或末尾可包含 <goto ref="某个 step 的 id">，表达流程
       跳转到先前已出现过的 step（如审批拒绝后回退到重审节点）。
    6. 主动触发入口保留 <class-path>，供 AI 根据源码分析请求参数、URL、DTO。
    7. 被动触发（如兜底事件监听）保留 <class-path>，但注明"无需测试脚本主动触发"。
    8. 如存在统一的定时调度器驱动多个 scheduler 节点，在 <scheduler-note> 中说明。

  文件名命名规范：
    {业务域}-{业务流程}-lifecycle.md
    示例：xxx-yyy-lifecycle.md

  ================================================================================
-->
<lifecycle-template version="1.0">

  <overview>
    <flow name="【替换为业务流程名称】">

      <!-- ========================================================== -->
      <!-- step：业务流程中的单个阶段                                   -->
      <!-- 属性说明：                                                   -->
      <!--   id         → 唯一标识，供 branch 或 goto 引用               -->
      <!--   name       → 步骤标识名，英文蛇形命名                       -->
      <!--   entry-type → 触发类型（http / scheduler / mq）              -->
      <!-- ========================================================== -->
      <step id="submit" name="submit" entry-type="http">
        <description>
          【替换】描述该步骤的业务行为
        </description>
        <class-path>
          【替换】触发该步骤的 Java 全限定类名
        </class-path>
      </step>

      <step id="scheduler-step" name="scheduler-step" entry-type="scheduler">
        <description>
          【替换】描述 scheduler 触发的具体业务
        </description>
        <class-path>
          【替换】被调度的 Handler / Executor 全限定类名
        </class-path>
      </step>

      <step id="action-step" name="action-step" entry-type="http">
        <description>
          【替换】描述该 http 调用的行为
        </description>
        <class-path>
          【替换】Facade / Controller 全限定类名
        </class-path>
      </step>

      <step id="mq-step" name="mq-step" entry-type="mq">
        <description>
          【替换】描述 MQ 回调的业务含义
        </description>
        <class-path>
          【替换】MQ Listener 全限定类名
        </class-path>
      </step>

      <!-- ========================================================== -->
      <!-- branch：分支节点                                             -->
      <!-- 属性说明：                                                   -->
      <!--   from-step  → 触发分支的前置 step 的 id 属性值              -->
      <!--   name       → 分支标识名                                    -->
      <!-- ========================================================== -->
      <branch from-step="action-step" name="【替换：分支标识名】">
        <description>
          【替换】描述分支的判断依据
        </description>

        <path name="approved" trigger="【替换：触发条件】">
          <step id="exec-step" name="exec-step" entry-type="scheduler">
            <description>
              【替换】例如：调用外部服务
            </description>
            <class-path>
              【替换】Executor 全限定类名
            </class-path>
          </step>
          <step id="exec-callback" name="exec-callback" entry-type="mq">
            <description>
              【替换】例如：等待外部结果 MQ 回调，订单进入终态
            </description>
            <class-path>
              【替换】MQ Listener 全限定类名
            </class-path>
          </step>
        </path>

        <!-- ======================================================== -->
        <!-- path + goto：分支结束后跳转到之前已出现的 step             -->
        <!-- 说明：当流程需要回退或循环时，在 path 末尾添加 <goto ref="..."> -->
        <!-- ======================================================== -->
        <path name="rejected" trigger="【替换：触发条件】">
          <step id="reject-handler" name="reject-handler" entry-type="scheduler">
            <description>
              【替换】例如：审批拒绝后回退订单状态，允许重新提交
            </description>
            <class-path>
              【替换】Handler 全限定类名
            </class-path>
          </step>
          <goto ref="action-step"/>
        </path>
      </branch>

      <step id="fallback" name="fallback" entry-type="scheduler">
        <description>
          【替换】例如：工作流重试耗尽时的兜底处理
          （被动事件监听，无需测试脚本主动触发）
        </description>
        <class-path>
          【替换】Event Listener 全限定类名
        </class-path>
      </step>

    </flow>

    <scheduler-note>
      <description>
        【替换】描述统一调度器的触发频率和等待策略，例如：
        以上所有 entry-type="scheduler" 的节点，均由 XxxScheduleJob 定时扫描驱动。
        默认每 X 秒执行一次（cron = */X * * * * ?）。
        端到端测试脚本在提交 http 请求后，需 sleep/轮询等待 scheduler 自动推进，
        或主动触发 XxxScheduleJob 以加速流程。
      </description>
      <class-path>
        【替换】调度器全限定类名
      </class-path>
    </scheduler-note>
  </overview>

  <!-- ============================================================ -->
  <!-- 二、标签速查表（集中说明所有合法 XML 标签的含义和约束）          -->
  <!-- ============================================================ -->
  <tag-reference>

    <tag name="step" desc="业务流程中的单个阶段，按 XML 出现顺序排列">
      <attribute name="id" required="true" desc="唯一标识，供 branch 或 goto 引用"/>
      <attribute name="name" required="true" desc="步骤标识名，英文蛇形命名"/>
      <attribute name="entry-type" required="true" desc="触发类型，可选值：http/scheduler/mq"/>
      <child name="description" desc="该步骤的业务行为说明"/>
      <child name="class-path" desc="触发该步骤的 Java 全限定类名"/>
    </tag>

    <tag name="branch" desc="分支节点，表达流程因条件不同而走不同路径">
      <attribute name="from-step" required="true" desc="触发分支的前置 step 的 id 属性值"/>
      <attribute name="name" required="true" desc="分支标识名"/>
      <child name="description" desc="分支的判断依据"/>
      <child name="path" required="true" desc="至少包含一条 path，每条 path 代表一个独立分支路径"/>
    </tag>

    <tag name="path" desc="分支路径，被 branch 包裹">
      <attribute name="name" required="true" desc="路径标识名，如 approved/rejected/timeout"/>
      <attribute name="trigger" required="true" desc="进入该路径的触发条件描述"/>
      <child name="step" desc="路径内部的步骤"/>
      <child name="goto" desc="可选，放在路径末尾用于跳转到先前已出现的 step"/>
    </tag>

    <tag name="goto" desc="流程跳转，通常放在 path 末尾表达回退或循环">
      <attribute name="ref" required="true" desc="目标 step 的 id，必须是 flow 中已出现的 step"/>
    </tag>

    <tag name="scheduler-note" desc="统一调度器说明，描述驱动多个 scheduler 节点的底层定时调度器">
      <child name="description" desc="调度频率、等待策略和测试建议"/>
      <child name="class-path" desc="调度器 Java 全限定类名"/>
    </tag>

  </tag-reference>

</lifecycle-template>
```
