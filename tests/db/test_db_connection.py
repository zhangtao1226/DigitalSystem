# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : test_db_connection.py
# @Desc      : 
# @Time      : 2025/12/1 16:39
# @Software  : PyCharm

from src.core.db import get_db, engine, Base
from src.models import User, Role

# 1. 创建所有数据库表（如果不存在）
Base.metadata.create_all(bind=engine)
print("✅ 数据库表创建成功（或已存在）")

# 2. 测试数据库会话和CRUD操作
def test_db_crud():
    db = next(get_db())  # 获取数据库会话

    try:
        # 清除测试数据（避免重复）
        db.query(User).delete()
        db.query(Role).delete()
        db.commit()
        print("✅ 清除历史测试数据")

        # 创建角色
        admin_role = Role(name="admin", desc="管理员角色")
        user_role = Role(name="user", desc="普通用户角色")
        db.add_all([admin_role, user_role])
        db.commit()
        print(f"✅ 创建角色：{admin_role}, {user_role}")

        # 创建用户并关联角色
        test_user = User(
            username="test_user",
            email="test@example.com",
            password_hash="hashed_password_123"
        )
        # 关联两个角色（多对多关系赋值）
        test_user.roles.append(admin_role)
        test_user.roles.append(user_role)
        db.add(test_user)
        db.commit()
        print(f"✅ 创建用户并关联角色：{test_user}")

        # 查询用户及其关联的角色
        queried_user = db.query(User).filter_by(username="test_user").first()
        queried_roles = queried_user.roles.all()  # 动态加载角色列表
        print(f"✅ 查询用户关联的角色：{[role.name for role in queried_roles]}")

        # 验证结果
        assert queried_user is not None
        assert len(queried_roles) == 2
        assert "admin" in [role.name for role in queried_roles]
        print("✅ 所有CRUD测试通过！")

    except Exception as e:
        db.rollback()  # 出错时回滚
        print(f"❌ 测试失败：{str(e)}")
        raise
    finally:
        db.close()  # 关闭会话

# if __name__ == "__main__":
#     # test_db_crud()
#     pass
