import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
} from '@mui/material';
import PrintIcon from '@mui/icons-material/Print';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import ListAltIcon from '@mui/icons-material/ListAlt';

function Navbar() {
  return (
    <AppBar position="static">
      <Toolbar>
        <PrintIcon sx={{ mr: 2 }} />
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          IoT Printer
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            color="inherit"
            component={RouterLink}
            to="/"
            startIcon={<PrintIcon />}
          >
            Dashboard
          </Button>
          <Button
            color="inherit"
            component={RouterLink}
            to="/upload"
            startIcon={<UploadFileIcon />}
          >
            Upload
          </Button>
          <Button
            color="inherit"
            component={RouterLink}
            to="/tasks"
            startIcon={<ListAltIcon />}
          >
            Tasks
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
}

export default Navbar; 