CREATE TABLE vm_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vm_name VARCHAR(255) NOT NULL,
    resource_group VARCHAR(255) NOT NULL,
    domain VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    vm_size VARCHAR(100) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    email_account VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);